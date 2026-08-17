"""Private fresh-process worker used only by reproducibility.py.

This file is invoked directly under ``python -I``. It binds imports to the
audited checkout before importing any executing generator module.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path


def _bind_audited_source() -> Path:
    script = Path(__file__)
    if script.is_symlink():
        raise SystemExit("worker source must not be a symlink")
    source_root = script.resolve(strict=True).parents[2]
    expected = os.environ.get("SIMPLE_SYNTH_AUDITED_SOURCE_ROOT")
    if expected is None or Path(expected) != source_root:
        raise SystemExit("worker source root does not equal the parent-audited root")
    package_parent = source_root / "src"
    original = [entry for entry in sys.path if entry and Path(entry).resolve() != package_parent]
    sys.path[:] = [str(package_parent), *original]
    package = __import__("simple_synthetic_eeg_generator")
    package_origin = Path(package.__file__).resolve(strict=True)
    expected_package = package_parent / "simple_synthetic_eeg_generator" / "__init__.py"
    if package_origin != expected_package:
        raise SystemExit("worker imported a generator package outside audited source")
    return source_root


def shuffled_order(subjects: tuple[str, ...]) -> tuple[str, ...]:
    """Return the frozen deterministic noncanonical computation order."""

    domain = b"simple-synthetic-eeg-generator/reproducibility-order/v1\n"
    result = tuple(
        sorted(subjects, key=lambda item: hashlib.sha256(domain + f"subject={item}\n".encode()).digest())
    )
    if result == subjects:
        raise RuntimeError("Frozen shuffled order unexpectedly equals canonical order")
    return result


def main() -> None:
    source_root = _bind_audited_source()
    from simple_synthetic_eeg_generator.settings import load_settings
    from simple_synthetic_eeg_generator.transaction import build_array_stage

    parser = argparse.ArgumentParser(prog="simple-synthetic-eeg-internal-worker")
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--simple-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--order", choices=("canonical", "shuffled"), required=True)
    args = parser.parse_args()
    if args.source_root != source_root:
        raise SystemExit("worker --source-root differs from audited source")
    settings = load_settings(args.settings)
    order = settings.subjects if args.order == "canonical" else shuffled_order(settings.subjects)
    build_array_stage(
        output=args.output,
        settings=settings,
        lock_file=args.lock_file,
        source_root=args.source_root,
        simple_commit=args.simple_commit,
        generation_order=order,
    )


if __name__ == "__main__":
    main()
