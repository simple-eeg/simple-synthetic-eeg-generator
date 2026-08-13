#!/usr/bin/env python3
"""Isolated entry point that imports the generator only from this checkout."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    script = Path(__file__)
    if script.is_symlink():
        raise SystemExit("generator launcher must not be a symlink")
    source_root = script.resolve(strict=True).parents[1]
    if source_root != source_root.resolve(strict=True):
        raise SystemExit("generator source root must be canonical")
    source_parent = source_root / "src"
    sys.path.insert(0, str(source_parent))
    from simple_synthetic_eeg_generator.cli import main as cli_main

    package = __import__("simple_synthetic_eeg_generator")
    expected = source_parent / "simple_synthetic_eeg_generator" / "__init__.py"
    if Path(package.__file__).resolve(strict=True) != expected:
        raise SystemExit("generator package did not resolve beneath this audited checkout")
    cli_main()


if __name__ == "__main__":
    main()
