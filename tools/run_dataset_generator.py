#!/usr/bin/env python3
"""Isolated launcher for the one-choice human-facing dataset build."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__)
    if script.is_symlink():
        raise SystemExit("dataset launcher must not be a symlink")
    source_root = script.resolve(strict=True).parents[1]
    if source_root != source_root.resolve(strict=True):
        raise SystemExit("generator source root must be canonical")
    source_parent = source_root / "src"
    sys.path.insert(0, str(source_parent))

    from simple_synthetic_eeg_generator.user_workflow import main as workflow_main

    package = __import__("simple_synthetic_eeg_generator")
    expected = source_parent / "simple_synthetic_eeg_generator" / "__init__.py"
    if Path(package.__file__).resolve(strict=True) != expected:
        raise SystemExit("generator package did not resolve beneath this audited checkout")
    workflow_main(source_root=source_root)


if __name__ == "__main__":
    main()
