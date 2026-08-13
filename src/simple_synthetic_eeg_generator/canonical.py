"""Canonical byte encodings for durable provenance and manifests."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence

from .errors import ContractError


def canonical_json_bytes(value: object) -> bytes:
    """Return sorted, compact UTF-8 JSON with no NaN and one final newline."""

    text = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (text + "\n").encode("utf-8")


def canonical_csv_bytes(
    rows: Iterable[Mapping[str, object]], fieldnames: Sequence[str]
) -> bytes:
    """Return RFC-4180-like UTF-8 CSV with a fixed column order and LF lines."""

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(fieldnames),
        extrasaction="raise",
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        missing = set(fieldnames) - set(row)
        if missing:
            raise ContractError(f"CSV row is missing columns: {sorted(missing)!r}")
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def write_new_bytes(path: Path, payload: bytes) -> None:
    """Write a new file exclusively, refusing symlinks and existing targets."""

    if path.exists() or path.is_symlink():
        raise ContractError(f"Refusing to overwrite: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def write_new_json(path: Path, value: object) -> None:
    write_new_bytes(path, canonical_json_bytes(value))


def write_new_csv(
    path: Path, rows: Iterable[Mapping[str, object]], fieldnames: Sequence[str]
) -> None:
    write_new_bytes(path, canonical_csv_bytes(rows, fieldnames))


def relative_files(root: Path, exclude: set[str] | None = None) -> list[Path]:
    """List regular non-symlink files in canonical relative-path order."""

    excluded = exclude or set()
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ContractError(f"Symlink is not permitted in a bundle: {path}")
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if rel not in excluded:
                files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def build_manifest(root: Path, manifest_name: str = "MANIFEST.sha256") -> bytes:
    """Build `sha256  relative/path` rows, excluding the manifest itself."""

    rows: list[str] = []
    for path in relative_files(root, {manifest_name}):
        rel = path.relative_to(root).as_posix()
        if str(PurePosixPath(rel)) != rel or rel.startswith("../"):
            raise ContractError(f"Non-canonical relative path: {rel!r}")
        rows.append(f"{sha256_file(path)}  {rel}\n")
    return "".join(rows).encode("utf-8")


def verify_manifest(root: Path, manifest_name: str = "MANIFEST.sha256") -> None:
    path = root / manifest_name
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"Missing regular {manifest_name}")
    expected = build_manifest(root, manifest_name)
    actual = path.read_bytes()
    if actual != expected:
        raise ContractError(f"{manifest_name} does not exactly match bundle bytes")
