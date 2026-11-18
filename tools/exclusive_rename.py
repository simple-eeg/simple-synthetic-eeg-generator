#!/usr/bin/env python3
"""Exclusively publish one sibling directory with a native no-replace rename.

This helper and its shared adapter use only the Python standard library.
It is invoked by the MATLAB packager through the selected checkout-local
Python interpreter; it never reads generator data or manifest contents.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from simple_synthetic_eeg_generator.platform_support import rename_directory_exclusive

EXIT_CONTRACT = 2
EXIT_EXISTS = 3
EXIT_RENAME = 4


def _fail(message: str, code: int) -> "None":
    print(f"exclusive promotion refused: {message}", file=sys.stderr)
    raise SystemExit(code)


def _absolute_canonical(path_text: str, *, must_exist: bool) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        _fail("both paths must be absolute", EXIT_CONTRACT)
    if must_exist:
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, OSError):
            _fail("source must exist", EXIT_CONTRACT)
    else:
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            _fail("destination path cannot be resolved", EXIT_CONTRACT)
    if path != resolved:
        _fail("paths must be canonical and contain no symlink component", EXIT_CONTRACT)
    return path


def _rename_exclusively(source: Path, destination: Path) -> None:
    try:
        rename_directory_exclusive(source, destination)
    except OSError as exc:
        if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
            _fail("destination appeared before exclusive promotion", EXIT_EXISTS)
        _fail(f"exclusive rename failed with errno {exc.errno}", EXIT_RENAME)


def promote(arguments: list[str]) -> None:
    """Validate and exclusively promote exactly two path arguments."""

    if len(arguments) != 2:
        _fail("expected exactly SOURCE_DIR DESTINATION", EXIT_CONTRACT)
    source = _absolute_canonical(arguments[0], must_exist=True)
    raw_destination = Path(arguments[1])
    if not raw_destination.is_absolute():
        _fail("both paths must be absolute", EXIT_CONTRACT)
    if os.path.lexists(raw_destination):
        _fail("destination already exists", EXIT_EXISTS)
    destination = _absolute_canonical(arguments[1], must_exist=False)
    if source.is_symlink() or not source.is_dir():
        _fail("source must be one existing non-symlink directory", EXIT_CONTRACT)
    if source == destination or source.parent != destination.parent:
        _fail("source and destination must be distinct siblings", EXIT_CONTRACT)
    parent = source.parent
    if not parent.is_dir() or parent.is_symlink() or parent.resolve(strict=True) != parent:
        _fail("shared parent must be one canonical non-symlink directory", EXIT_CONTRACT)
    if source.stat(follow_symlinks=False).st_dev != parent.stat(follow_symlinks=False).st_dev:
        _fail("source and destination parent must be on one filesystem", EXIT_CONTRACT)

    _rename_exclusively(source, destination)
    if os.path.lexists(source) or not destination.is_dir() or destination.is_symlink():
        _fail("Exclusive rename returned success without exact directory promotion", EXIT_RENAME)


def main() -> None:
    promote(sys.argv[1:])


if __name__ == "__main__":
    main()
