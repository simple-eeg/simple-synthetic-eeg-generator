"""Strict, atomic, no-overwrite Python-stage transaction."""

from __future__ import annotations

import contextlib
import os
import re
import secrets
import tempfile
import sys
from pathlib import Path
from typing import Iterator
from typing import Sequence

from .canonical import build_manifest, write_new_bytes, write_new_csv, write_new_json
from .audit import audit_checkout, require_audited_module_origins, require_tracked_input
from .environment import runtime_environment_receipt
from .platform_support import rename_directory_exclusive, sync_directory
from .errors import ContractError, TransactionError
from .model import canonical_array_bytes, generate_subject
from .provenance import (
    dataset_list_rows,
    ground_truth_fields,
    ground_truth_rows,
    realised_parameter_fields,
    realised_parameter_row,
    seed_manifest_fields,
    seed_manifest_rows,
)
from .settings import FrozenSettings, SIMPLE_INPUT_CONTRACT, TESTED_SIMPLE_COMMIT
from .validation import validate_cohort, validate_staged_array

ARRAY_NAME = "sub-{subject}_ses-01_run-01_eeg.f32le"
ASSET_NAMES = (
    "README.md",
    "CITATION.cff",
    "CC-BY-4.0.txt",
)
DATASET_LIST_FIELDS = ["subjectID", "sessionID", "runID", "path_raw", "EEGfile_raw"]
FORBIDDEN_SUFFIXES = {".set", ".fdt", ".mat", ".log", ".diary"}
FORBIDDEN_TEXT = (
    re.compile(re.escape("/" + "Users" + "/"), re.IGNORECASE),
    re.compile(r"[A-Z]:\\\\" + "Users" + r"\\\\", re.IGNORECASE),
    re.compile(r"Petal", re.IGNORECASE),
    re.compile(r"NOCI[-_ ]?Prem", re.IGNORECASE),
)


@contextlib.contextmanager
def controlled_mplconfig(parent: Path) -> Iterator[None]:
    """Provide a writable ephemeral Matplotlib cache before NeuroDSP imports."""

    old = os.environ.get("MPLCONFIGDIR")
    with tempfile.TemporaryDirectory(prefix=".simple-synth-mplconfig-", dir=parent) as directory:
        os.environ["MPLCONFIGDIR"] = directory
        try:
            yield
        finally:
            if old is None:
                os.environ.pop("MPLCONFIGDIR", None)
            else:
                os.environ["MPLCONFIGDIR"] = old


def _fsync_directory(path: Path) -> None:
    sync_directory(path)


def exclusive_atomic_rename(source: Path, destination: Path) -> None:
    """Publish a complete directory without replacing any existing destination."""
    try:
        rename_directory_exclusive(source, destination)
    except OSError as exc:
        raise TransactionError(
            f"Exclusive atomic promotion failed without overwrite (errno {exc.errno})"
        ) from exc


def _refuse_existing(path: Path, label: str) -> None:
    if path.exists() or path.is_symlink():
        raise TransactionError(f"{label} already exists; refusing overwrite")


def require_canonical_absent_output(output: Path) -> None:
    """Require an absolute, absent, lexically canonical path under a canonical parent."""

    if not output.is_absolute():
        raise TransactionError("Output must be an explicit absolute path")
    parent = output.parent
    try:
        canonical_parent = parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise TransactionError("Output parent must already exist") from exc
    if parent != canonical_parent or parent.is_symlink() or not parent.is_dir():
        raise TransactionError("Output parent and all components must be canonical non-symlinks")
    if output != canonical_parent / output.name:
        raise TransactionError("Output path is not lexically canonical")
    _refuse_existing(output, "Final output")


def refuse_stale_partials(output: Path) -> None:
    stale = sorted(output.parent.glob(output.name + ".partial.*"))
    if stale:
        raise TransactionError(
            "A prior partial exists; inspect and remove that exact failed-build artifact before retrying"
        )


def _scan_stage(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ContractError("Stage contains a symlink")
        if path.is_file():
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                raise ContractError(f"Python stage contains forbidden output type: {path.suffix}")
            if path.suffix.lower() in {".json", ".csv", ".md", ".txt"}:
                text = path.read_text(encoding="utf-8")
                for pattern in FORBIDDEN_TEXT:
                    if pattern.search(text):
                        raise ContractError(f"Stage metadata contains forbidden source text in {path.name}")
    forbidden_names = {
        "screening_package.mat",
        "screening_decisions.mat",
        "exclude_mask.csv",
    }
    if any(path.name in forbidden_names for path in root.rglob("*")):
        raise ContractError("Generator must not prepopulate any screening decision")


def build_array_stage(
    *,
    output: Path,
    settings: FrozenSettings,
    source_root: Path,
    generation_order: Sequence[str] | None = None,
) -> Path:
    """Generate, validate, and atomically promote one immutable array stage."""

    require_canonical_absent_output(output)
    parent = output.parent
    if source_root.resolve() == output.resolve() or source_root.resolve() in output.resolve().parents:
        raise TransactionError("Generated stages must remain outside the Git source tree")
    audit = audit_checkout(source_root)
    require_tracked_input(source_root, settings.source_path, "config/")
    refuse_stale_partials(output)
    stage = output.with_name(output.name + ".partial." + secrets.token_hex(12))
    _refuse_existing(stage, "Unique partial stage")
    generator_commit = str(audit["head"])
    os.mkdir(stage, 0o755)
    try:
        module_origins = require_audited_module_origins(source_root)
        runtime = runtime_environment_receipt(source_root)
        order = tuple(settings.subjects if generation_order is None else generation_order)
        if len(order) != len(settings.subjects) or set(order) != set(settings.subjects):
            raise ContractError("Generation order must be a permutation of exact subjects 001..031")
        with controlled_mplconfig(parent):
            by_subject = {
                subject_id: generate_subject(subject_id, settings.values) for subject_id in order
            }
        results = [by_subject[subject_id] for subject_id in settings.subjects]
        validation = validate_cohort(results, settings.values)

        write_new_bytes(stage / "provenance" / "generator_settings.json", settings.canonical_bytes)
        realised_rows = [realised_parameter_row(result) for result in results]
        write_new_csv(
            stage / "provenance" / "realised_parameters.csv",
            realised_rows,
            realised_parameter_fields(),
        )
        assets = source_root / "dataset_assets"
        for name in ASSET_NAMES:
            asset = assets / name
            require_tracked_input(source_root, asset, "dataset_assets/")
            write_new_bytes(stage / "dataset_assets" / name, asset.read_bytes())
        write_new_csv(
            stage / "provenance" / "seed_manifest.csv",
            seed_manifest_rows(results),
            seed_manifest_fields(),
        )
        truth_rows = [row for result in results for row in ground_truth_rows(result, settings.values)]
        write_new_csv(
            stage / "provenance" / "ground_truth_manifest.csv",
            truth_rows,
            ground_truth_fields(),
        )
        write_new_json(stage / "provenance" / "python_validation.json", validation)
        receipt = {
            "schema": "simple-synthetic-array-stage-receipt-v3",
            "status": "passed",
            "generator_commit": generator_commit,
            "tested_simple_commit": TESTED_SIMPLE_COMMIT,
            "simple_input_contract": SIMPLE_INPUT_CONTRACT,
            "runtime": runtime,
            "static_audit": audit,
            "executing_generator_module_origins": module_origins,
            "subject_count": len(results),
            "sample_count_per_subject": int(settings.values["dataset"]["sample_count"]),
            "array_encoding": "IEEE-754 little-endian float32",
            "contains_real_data": False,
            "contains_screening_decisions": False,
            "build_variant": "single-validated-cohort",
        }
        write_new_json(stage / "provenance" / "build_receipt.json", receipt)
        write_new_csv(
            stage / "data_lists" / "dataset_list.csv",
            dataset_list_rows(settings.subjects),
            DATASET_LIST_FIELDS,
        )
        sample_count = int(settings.values["dataset"]["sample_count"])
        for result in results:
            path = stage / "staging" / "arrays" / ARRAY_NAME.format(subject=result.subject_id)
            write_new_bytes(path, canonical_array_bytes(result.staged_float32, "float32"))
            validate_staged_array(path, result, sample_count)
        _scan_stage(stage)
        write_new_bytes(stage / "MANIFEST.sha256", build_manifest(stage))
        _fsync_directory(stage)
        _fsync_directory(parent)
        _refuse_existing(output, "Final output")
        exclusive_atomic_rename(stage, output)
        _fsync_directory(parent)
        return output
    except BaseException as exc:
        marker = stage / "BUILD_FAILED.json"
        if stage.is_dir() and not marker.exists():
            try:
                write_new_json(
                    marker,
                    {
                        "schema": "simple-synthetic-build-failure-v1",
                        "status": "failed-not-promoted",
                        "error_type": type(exc).__name__,
                    },
                )
            except BaseException:
                pass
        raise
