"""Build a deterministic post-evaluation CareTrust evidence manifest.

This manifest describes repository state and locally testable artifacts added
after the frozen 20-case model evaluation. It does not rerun, replace, or
reinterpret that evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_VERSION = "caretrust.post-evaluation-evidence.v0.4"
FROZEN_EVALUATION_RUN_ID = "20260730T085655.959974Z"
FROZEN_EVALUATION_REFERENCES = (
    "artifacts/evaluation/frozen-run-config.json",
    f"artifacts/evaluation/{FROZEN_EVALUATION_RUN_ID}/frozen-config.json",
    f"artifacts/evaluation/{FROZEN_EVALUATION_RUN_ID}/summary.json",
    f"artifacts/evaluation/{FROZEN_EVALUATION_RUN_ID}/REPORT.md",
)

ARTIFACT_PATTERNS = (
    "README.md",
    ".specifica/trl3-poc/*.md",
    "pyproject.toml",
    "requirements.lock",
    "artifacts/validation/**/*.json",
    "artifacts/validation/**/*.jsonl",
    "artifacts/validation/**/*.md",
    "demo/*.html",
    "demo/*.css",
    "demo/*.js",
    "demo/*.md",
    "docs/standards/**/*.json",
    "docs/standards/**/*.md",
    "docs/use-cases/*.md",
    "fixtures/**/*.json",
    "fixtures/**/*.txt",
    "schemas/*.json",
    "scripts/*.py",
    "src/caretrust/**/*.py",
    "tests/*.py",
    *FROZEN_EVALUATION_REFERENCES,
)

EVIDENCE_STATUS_REGISTRY = (
    ROOT / "docs" / "standards" / "evidence-status-registry.json"
)

EXPLICIT_NON_CLAIMS = (
    "cross-organization federation",
    "FHIR conformance or independent FHIR interoperability",
    "OID4VC deployment or protocol conformance",
    "a deployed credential issuer, verifier, or wallet",
    "live-registry integration or automated source verification",
    "EHR integration or SMART App Launch conformance",
    "production identity proofing, authorization, security, or readiness",
)

def _load_implementation_status_matrix() -> tuple[dict[str, Any], ...]:
    registry = json.loads(EVIDENCE_STATUS_REGISTRY.read_text(encoding="utf-8"))
    known_statuses = {
        item["id"]
        for item in registry["statuses"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    matrix: list[dict[str, Any]] = []
    for capability in registry["capabilities"]:
        if not capability.get("include_in_manifest", False):
            continue
        status = capability["evidence_status"]
        if status not in known_statuses:
            raise ValueError(
                f"unknown evidence status {status!r} for "
                f"{capability['capability_id']}"
            )
        matrix.append(
            {
                "capability_id": capability["capability_id"],
                "status": status,
                "evidence": capability["evidence"],
                "boundary": capability["boundary"],
            }
        )
    return tuple(matrix)


IMPLEMENTATION_STATUS_MATRIX = _load_implementation_status_matrix()


class ManifestBuildError(RuntimeError):
    """Raised when evidence inputs or repository state cannot be verified."""


def _run_git(root: Path, *args: str, strip_output: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ManifestBuildError(f"git {' '.join(args)} failed: {detail.strip()}") from exc
    if strip_output:
        return result.stdout.strip()
    return result.stdout.rstrip("\r\n")


def _validate_https_repository_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ManifestBuildError(
            "public repository URL must be an HTTPS URL without credentials, "
            "query, or fragment"
        )
    return value.rstrip("/")


def _validate_caller_value(value: str, field: str) -> str:
    if not value.strip() or "\n" in value or "\r" in value:
        raise ManifestBuildError(f"{field} must be a nonblank single-line value")
    return value.strip()


def _verify_release_identifiers(
    root: Path,
    *,
    release_tag: str,
    release_commit: str,
) -> tuple[str, str]:
    tag = _validate_caller_value(release_tag, "release_tag")
    commit = _validate_caller_value(release_commit, "release_commit").lower()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ManifestBuildError("release_commit must be a full 40-character SHA-1")
    resolved_commit = _run_git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
    resolved_tag = _run_git(root, "rev-list", "-n", "1", f"refs/tags/{tag}")
    if resolved_commit != commit:
        raise ManifestBuildError("release_commit did not resolve to the supplied commit")
    if resolved_tag != commit:
        raise ManifestBuildError("release_tag does not resolve to release_commit")
    return tag, commit


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManifestBuildError(f"artifact is outside repository root: {path}") from exc


def collect_artifact_paths(
    root: Path,
    *,
    output_path: Path | None = None,
    patterns: Sequence[str] = ARTIFACT_PATTERNS,
) -> list[Path]:
    """Return the stable, sorted artifact set selected by the manifest profile."""

    excluded = output_path.resolve() if output_path is not None else None
    tracked = set(_run_git(root, "ls-files").splitlines())
    selected: dict[str, Path] = {}
    for pattern in patterns:
        matches = list(root.glob(pattern))
        if not matches:
            raise ManifestBuildError(f"evidence pattern matched no files: {pattern}")
        for path in matches:
            if not path.is_file() or (excluded is not None and path.resolve() == excluded):
                continue
            relative = _relative_path(root, path)
            if relative.startswith(
                "artifacts/validation/poc-evidence-manifest-"
            ):
                continue
            if relative not in tracked:
                continue
            selected[relative] = path
    return [selected[relative] for relative in sorted(selected)]


def artifact_records(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    records = [
        {
            "path": _relative_path(root, path),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in paths
    ]
    return sorted(records, key=lambda item: item["path"])


def _status_path(entry: str) -> str:
    value = entry[3:] if len(entry) >= 4 else entry
    if " -> " in value:
        value = value.split(" -> ", 1)[1]
    return value.strip('"')


def repository_state(root: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    """Capture current commit and exact porcelain worktree entries."""

    head_commit = _run_git(root, "rev-parse", "HEAD")
    abbreviated_ref = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    head_ref = None if abbreviated_ref == "HEAD" else abbreviated_ref
    raw_status = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        strip_output=False,
    )
    entries = sorted(line for line in raw_status.splitlines() if line)

    if output_path is not None:
        try:
            output_relative = output_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            output_relative = None
        if output_relative is not None:
            entries = [
                entry for entry in entries if _status_path(entry) != output_relative
            ]

    return {
        "head_commit": head_commit,
        "head_ref": head_ref,
        "is_dirty": bool(entries),
        "status_entries": entries,
        "tracked_change_count": sum(not entry.startswith("??") for entry in entries),
        "untracked_file_count": sum(entry.startswith("??") for entry in entries),
    }


def _artifact_set_sha256(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        records,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_manifest(
    *,
    root: Path,
    test_result_reference: str,
    public_repository_url: str,
    release_tag: str,
    release_commit: str,
    output_path: Path | None = None,
    artifact_paths: Sequence[Path] | None = None,
    verify_release: bool = True,
) -> dict[str, Any]:
    """Build the deterministic manifest as a JSON-serializable mapping."""

    root = root.resolve()
    test_reference = _validate_caller_value(
        test_result_reference,
        "test_result_reference",
    )
    repository_url = _validate_https_repository_url(public_repository_url)
    if verify_release:
        tag, commit = _verify_release_identifiers(
            root,
            release_tag=release_tag,
            release_commit=release_commit,
        )
    else:
        tag = _validate_caller_value(release_tag, "release_tag")
        commit = _validate_caller_value(release_commit, "release_commit").lower()

    paths = (
        list(artifact_paths)
        if artifact_paths is not None
        else collect_artifact_paths(root, output_path=output_path)
    )
    records = artifact_records(root, paths)
    records_by_path = {record["path"]: record for record in records}
    frozen_references = []
    for path in FROZEN_EVALUATION_REFERENCES:
        record = records_by_path.get(path)
        if record is None:
            raise ManifestBuildError(
                f"frozen evaluation reference is missing from artifact set: {path}"
            )
        frozen_references.append(
            {
                "path": record["path"],
                "sha256": record["sha256"],
            }
        )

    return {
        "manifest_version": MANIFEST_VERSION,
        "evidence_scope": {
            "kind": "post_evaluation_repository_and_standards_evidence",
            "synthetic_only": True,
            "frozen_model_evaluation_recomputed": False,
            "statement": (
                "This manifest records post-evaluation code, contracts, local "
                "tests, and repository state. It does not rerun, replace, expand, "
                "or reinterpret the frozen 20-case model evaluation."
            ),
        },
        "repository_state": repository_state(root, output_path=output_path),
        "publication": {
            "public_repository_url": repository_url,
            "release_tag": tag,
            "release_commit": commit,
            "identifiers_supplied_by_caller": True,
        },
        "testing": {
            "result_reference": test_reference,
            "reference_supplied_by_caller": True,
            "tests_executed_by_manifest_generator": False,
        },
        "frozen_model_evaluation": {
            "run_id": FROZEN_EVALUATION_RUN_ID,
            "case_count": 20,
            "state": "referenced_only_not_recomputed_or_replaced",
            "references": frozen_references,
        },
        "implementation_status_matrix": [
            dict(item) for item in IMPLEMENTATION_STATUS_MATRIX
        ],
        "explicit_non_claims": list(EXPLICIT_NON_CLAIMS),
        "artifact_hash_algorithm": "sha256",
        "artifact_set_sha256": _artifact_set_sha256(records),
        "artifacts": records,
    }


def manifest_json(manifest: dict[str, Any]) -> str:
    """Serialize a manifest using one stable representation."""

    return json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic post-evaluation evidence without changing the "
            "frozen 20-case model evaluation."
        )
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--test-result-reference", required=True)
    parser.add_argument("--public-repository-url", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--release-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output_path = args.output.resolve() if args.output is not None else None
    try:
        manifest = build_manifest(
            root=args.root,
            test_result_reference=args.test_result_reference,
            public_repository_url=args.public_repository_url,
            release_tag=args.release_tag,
            release_commit=args.release_commit,
            output_path=output_path,
        )
        rendered = manifest_json(manifest)
        if output_path is None:
            sys.stdout.write(rendered)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered, encoding="utf-8", newline="\n")
            print(output_path)
    except ManifestBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
