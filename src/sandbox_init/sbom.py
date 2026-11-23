from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REQUIRED_PACKAGES: tuple[str, ...] = ("z3-solver", "pydantic")
CLUSTER_REQUIRED_PACKAGES: tuple[str, ...] = (
    "pydantic",
    "z3-solver",
    "duckdb",
    "mcp",
    "httpx",
)
FORBIDDEN_PATH_TOKENS: tuple[str, ...] = ("/home/", "/Users/")


class SbomSanitizeReport(BaseModel):
    """Deterministic CycloneDX PEP 610 sanitization and hygiene verdict."""

    model_config = ConfigDict(frozen=True)

    input_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    bom_format: str = Field(min_length=1)
    component_count: int = Field(ge=0)
    removed_file_refs: int = Field(ge=0)
    remaining_external_refs: int = Field(ge=0)
    verified: bool
    component_fingerprints: list[tuple[str, str, str]] = Field(
        default_factory=list
    )


def _sanitize_external_refs_list(
    raw_refs: Any,
) -> tuple[list[dict[str, Any]], int, int]:
    if not isinstance(raw_refs, list):
        return [], 0, 0
    kept: list[dict[str, Any]] = []
    removed = 0
    for item in raw_refs:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if url.startswith("file://"):
            removed += 1
        else:
            kept.append(item)
    return kept, removed, len(kept)


def _sanitize_component_tree(component: dict[str, Any]) -> tuple[int, int]:
    removed_total = 0
    remaining_total = 0
    if "externalReferences" in component:
        kept, removed, remaining = _sanitize_external_refs_list(
            component.get("externalReferences")
        )
        component["externalReferences"] = kept
        removed_total += removed
        remaining_total += remaining

    nested = component.get("components")
    if isinstance(nested, list):
        for child in nested:
            if isinstance(child, dict):
                c_rem, c_keep = _sanitize_component_tree(child)
                removed_total += c_rem
                remaining_total += c_keep
    return removed_total, remaining_total


def sanitize_cyclonedx_bom(
    bom: Mapping[str, Any],
) -> tuple[dict[str, Any], int, int]:
    """Strip PEP 610 local file:// externalReferences from a CycloneDX BOM."""
    sanitized: dict[str, Any] = copy.deepcopy(dict(bom))
    removed_total = 0
    remaining_total = 0

    if "externalReferences" in sanitized:
        kept, rem, rem_keep = _sanitize_external_refs_list(
            sanitized.get("externalReferences")
        )
        sanitized["externalReferences"] = kept
        removed_total += rem
        remaining_total += rem_keep

    metadata = sanitized.get("metadata")
    if isinstance(metadata, dict):
        meta_comp = metadata.get("component")
        if isinstance(meta_comp, dict):
            m_rem, m_keep = _sanitize_component_tree(meta_comp)
            removed_total += m_rem
            remaining_total += m_keep

    components = sanitized.get("components")
    if isinstance(components, list):
        for comp in components:
            if isinstance(comp, dict):
                c_rem, c_keep = _sanitize_component_tree(comp)
                removed_total += c_rem
                remaining_total += c_keep

    return sanitized, removed_total, remaining_total


def extract_component_fingerprints(
    bom: Mapping[str, Any],
) -> list[tuple[str, str, str]]:
    """Extract sorted (name, version, purl) tuples from BOM components."""
    raw_components = bom.get("components")
    if not isinstance(raw_components, list):
        return []
    items: list[tuple[str, str, str]] = []
    for comp in raw_components:
        if not isinstance(comp, dict) or "name" not in comp:
            continue
        name = str(comp["name"])
        version = str(comp.get("version", ""))
        purl = str(comp.get("purl", ""))
        items.append((name, version, purl))
    return sorted(items)


def verify_sanitized_bom(
    bom: Mapping[str, Any],
    required_packages: Sequence[str] = DEFAULT_REQUIRED_PACKAGES,
) -> list[tuple[str, str, str]]:
    """Assert CycloneDX schema format, path hygiene, and required packages."""
    bom_format = str(bom.get("bomFormat", ""))
    if bom_format != "CycloneDX":
        msg = f"Invalid bomFormat={bom_format!r}; expected 'CycloneDX'"
        raise ValueError(msg)

    serialized = json.dumps(bom, sort_keys=True)
    if "file://" in serialized:
        msg = "Sanitized CycloneDX SBOM still contains forbidden 'file://' URI"
        raise ValueError(msg)

    for token in FORBIDDEN_PATH_TOKENS:
        if token in serialized:
            msg = f"Sanitized CycloneDX SBOM leaked host path token {token!r}"
            raise ValueError(msg)

    fingerprints = extract_component_fingerprints(bom)
    present_names = {fp[0] for fp in fingerprints}
    missing = sorted(set(required_packages) - present_names)
    if missing:
        msg = f"CycloneDX SBOM missing required packages: {missing}"
        raise ValueError(msg)

    return fingerprints


def sanitize_sbom_file(
    input_path: Path,
    output_path: Path | None = None,
    *,
    verify: bool = True,
    required_packages: Sequence[str] = DEFAULT_REQUIRED_PACKAGES,
    sort_keys: bool = True,
) -> SbomSanitizeReport:
    """Sanitize a CycloneDX JSON file on disk and optionally verify hygiene."""
    resolved_in = input_path.resolve()
    if not resolved_in.is_file():
        msg = f"Input SBOM file not found: {resolved_in}"
        raise FileNotFoundError(msg)

    resolved_out = (
        resolved_in if output_path is None else output_path.resolve()
    )
    raw_data = json.loads(resolved_in.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        msg = "Expected top-level JSON object in CycloneDX SBOM"
        raise ValueError(msg)

    sanitized, removed, remaining = sanitize_cyclonedx_bom(raw_data)
    if verify:
        fingerprints = verify_sanitized_bom(
            sanitized, required_packages=required_packages
        )
    else:
        fingerprints = extract_component_fingerprints(sanitized)

    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    formatted = json.dumps(sanitized, indent=2, sort_keys=sort_keys) + "\n"
    resolved_out.write_text(formatted, encoding="utf-8")

    return SbomSanitizeReport(
        input_path=str(resolved_in),
        output_path=str(resolved_out),
        bom_format=str(sanitized.get("bomFormat", "unknown")),
        component_count=len(fingerprints),
        removed_file_refs=removed,
        remaining_external_refs=remaining,
        verified=verify,
        component_fingerprints=fingerprints,
    )


def generate_and_sanitize_sbom(
    output_path: Path,
    *,
    repo_root: Path | None = None,
    cyclonedx_bin: Path | None = None,
    verify: bool = True,
    required_packages: Sequence[str] = DEFAULT_REQUIRED_PACKAGES,
    sort_keys: bool = True,
) -> SbomSanitizeReport:
    """Run cyclonedx-py environment and sanitize PEP 610 file:// references."""
    work_root = (
        DEFAULT_REPO_ROOT if repo_root is None else repo_root
    ).resolve()
    repo_cdx = work_root / ".venv" / "bin" / "cyclonedx-py"
    fallback_cdx = Path(sys.executable).parent / "cyclonedx-py"
    default_cdx = repo_cdx if repo_cdx.is_file() else fallback_cdx
    cdx_bin = default_cdx if cyclonedx_bin is None else cyclonedx_bin
    if not cdx_bin.is_file():
        msg = f"cyclonedx-py binary not found at {cdx_bin}"
        raise FileNotFoundError(msg)

    resolved_out = output_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(cdx_bin), "environment", "-o", str(resolved_out)],
        cwd=work_root,
        check=True,
    )
    return sanitize_sbom_file(
        resolved_out,
        resolved_out,
        verify=verify,
        required_packages=required_packages,
        sort_keys=sort_keys,
    )


def _format_summary_line(report: SbomSanitizeReport) -> str:
    out_name = Path(report.output_path).name
    return (
        f"[sbom] file={out_name} format={report.bom_format} "
        f"components={report.component_count} "
        f"removed_file_refs={report.removed_file_refs} "
        f"remaining_refs={report.remaining_external_refs} "
        f"verified={report.verified}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for CycloneDX PEP 610 file:// sanitization (CAPA-007)."""
    parser = argparse.ArgumentParser(
        description="Sanitize PEP 610 file:// externalReferences in CycloneDX."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("sbom.cdx.json"),
        help="Input CycloneDX SBOM JSON path (default: sbom.cdx.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CycloneDX SBOM JSON path (defaults to in-place --input).",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Invoke cyclonedx-py environment before sanitizing target file.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Optional working directory when running with --generate.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify CycloneDX format, zero file:///home leaks, and packages.",
    )
    parser.add_argument(
        "--require-pkg",
        action="append",
        dest="required_packages",
        default=None,
        help="Package name required during --verify (may be passed multiple).",
    )
    parser.add_argument(
        "--no-sort-keys",
        action="store_true",
        help="Preserve original JSON key order instead of sorting keys.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "summary"),
        default="json",
        help="CLI output format: 'json' report or one-line 'summary'.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    req_pkgs: Sequence[str] = (
        tuple(args.required_packages)
        if args.required_packages
        else DEFAULT_REQUIRED_PACKAGES
    )
    sort_keys = not bool(args.no_sort_keys)
    target_out = args.input if args.output is None else args.output

    if args.generate:
        report = generate_and_sanitize_sbom(
            target_out,
            repo_root=args.repo_root,
            verify=bool(args.verify),
            required_packages=req_pkgs,
            sort_keys=sort_keys,
        )
    else:
        report = sanitize_sbom_file(
            args.input,
            target_out,
            verify=bool(args.verify),
            required_packages=req_pkgs,
            sort_keys=sort_keys,
        )

    if args.format == "summary":
        print(_format_summary_line(report))
    else:
        print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
