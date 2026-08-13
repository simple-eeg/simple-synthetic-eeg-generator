"""Static source, dependency, and human-data boundary audit."""

from __future__ import annotations

import ast
import ctypes
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from .errors import ContractError

ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "ast",
    "contextlib",
    "copy",
    "ctypes",
    "csv",
    "dataclasses",
    "errno",
    "hashlib",
    "importlib",
    "io",
    "json",
    "math",
    "os",
    "pathlib",
    "platform",
    "re",
    "secrets",
    "shutil",
    "subprocess",
    "sys",
    "tempfile",
    "typing",
    "unittest",
    "numpy",
    "scipy",
    "neurodsp",
    "simple_synthetic_eeg_generator",
}
FORBIDDEN_SUFFIXES = {
    ".bdf", ".bin", ".csv", ".dat", ".edf", ".eeg", ".f32le", ".fdt",
    ".mat", ".npy", ".npz", ".set", ".vhdr", ".vmrk",
}
ALLOWED_UNTRACKED_ROOTS = {".venv"}
ALLOWED_IGNORED_CACHE_COMPONENTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
FORBIDDEN_OUTPUT_COMPONENTS = {"data", "outputs", "provenance", "build", "dist"}
ALLOWED_SUFFIXES = {".cff", ".in", ".json", ".lock", ".m", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
SPECIAL_NAMES = {".gitignore", "LICENSE"}
FORBIDDEN_SOURCE_PATH_TEXT = (
    "/" + "Users" + "/",
    "/" + "Volumes" + "/",
    "file" + "://",
    "\\\\" + "Users" + "\\",
)
FORBIDDEN_CONFIG_TEXT = ("petal", "noci-prem", "participant", "patient", "hospital", "nhs")


def _git(source_root: Path, *arguments: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(source_root), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if process.returncode != 0:
        raise ContractError(f"Git audit command failed: {' '.join(arguments)}")
    return process.stdout


def _source_paths_by_name(source_root: Path) -> list[Path]:
    """List every checkout path by name only, pruning Git and the approved venv."""

    found: list[Path] = []
    for directory, names, files in os.walk(source_root, topdown=True, followlinks=False):
        current = Path(directory)
        relative_directory = current.relative_to(source_root)
        if relative_directory == Path("."):
            names[:] = [name for name in names if name != ".git" and name not in ALLOWED_UNTRACKED_ROOTS]
        else:
            names[:] = list(names)
        for name in names:
            found.append(current / name)
        for name in files:
            found.append(current / name)
    return found


def _audit_all_checkout_names(source_root: Path, tracked: set[str]) -> dict[str, int]:
    """Reject ignored data/output names without opening any ignored file."""

    ignored_or_untracked = 0
    allowed_cache_paths = 0
    audited_paths = 0
    tracked_directories = {
        "/".join(parts[:index])
        for relative in tracked
        for parts in [relative.split("/")]
        for index in range(1, len(parts))
    }
    for path in _source_paths_by_name(source_root):
        audited_paths += 1
        relative = path.relative_to(source_root).as_posix()
        if path.is_symlink():
            raise ContractError(f"Symlink is forbidden outside the allowlisted virtual environment: {relative}")
        is_tracked = relative in tracked or (path.is_dir() and relative in tracked_directories)
        if not is_tracked:
            ignored_or_untracked += 1
            suffix = path.suffix.lower()
            parts = set(path.relative_to(source_root).parts)
            output_shaped = (
                suffix in FORBIDDEN_SUFFIXES
                or bool(parts & FORBIDDEN_OUTPUT_COMPONENTS)
                or path.name == "MANIFEST.sha256"
                or "BUILD_FAILED" in path.name
                or ".partial." in relative
                or path.name.endswith(".building")
            )
            if output_shaped:
                raise ContractError(
                    f"Ignored or untracked data/workflow-output-like path is forbidden: {relative}"
                )
            if parts & ALLOWED_IGNORED_CACHE_COMPONENTS or path.name == ".coverage":
                allowed_cache_paths += 1
                continue
            raise ContractError(f"Unexpected ignored or untracked source-tree path: {relative}")
    return {
        "audited_paths_outside_git_and_venv": audited_paths,
        "ignored_or_untracked_files_outside_venv": ignored_or_untracked,
        "allowed_ignored_cache_paths_outside_venv": allowed_cache_paths,
        "data_or_user_output_paths_outside_venv": 0,
    }


def require_audited_module_origins(source_root: Path) -> dict[str, str]:
    """Prove every loaded generator module is the exact audited checkout copy."""

    package_root = source_root.resolve(strict=True) / "src" / "simple_synthetic_eeg_generator"
    origins: dict[str, str] = {}
    for name, module in sorted(sys.modules.items()):
        if name != "simple_synthetic_eeg_generator" and not name.startswith(
            "simple_synthetic_eeg_generator."
        ):
            continue
        raw_origin = getattr(module, "__file__", None)
        if raw_origin is None:
            raise ContractError(f"Loaded generator module has no file origin: {name}")
        origin = Path(raw_origin)
        try:
            relative = origin.resolve(strict=True).relative_to(package_root).as_posix()
        except (FileNotFoundError, ValueError) as exc:
            raise ContractError(
                f"Loaded generator module is outside the exact audited source root: {name}"
            ) from exc
        if origin.is_symlink() or origin.suffix != ".py":
            raise ContractError(f"Loaded generator module origin is not an approved source file: {name}")
        origins[name] = relative
    if "simple_synthetic_eeg_generator" not in origins:
        raise ContractError("Generator package is not loaded from the audited source root")
    return origins


def audit_checkout(source_root: Path) -> dict[str, object]:
    """Bind generation to one clean tracked source tree and audit every file."""

    if not source_root.is_absolute() or not source_root.is_dir() or source_root.is_symlink():
        raise ContractError("Generator source root must be an absolute non-symlink directory")
    try:
        canonical_root = source_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ContractError("Generator source root does not exist") from exc
    if source_root != canonical_root:
        raise ContractError("Generator source root and every path component must be canonical")
    root = Path(_git(source_root, "rev-parse", "--show-toplevel").decode().strip())
    if root != source_root:
        raise ContractError("Source root is not the exact Git top level")
    head = _git(source_root, "rev-parse", "HEAD").decode("ascii").strip()
    if len(head) != 40 or any(char not in "0123456789abcdef" for char in head):
        raise ContractError("Generator HEAD is not a lowercase 40-hex commit")
    if _git(source_root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ContractError("Generator checkout must be completely clean, including untracked files")
    tracked = [item for item in _git(source_root, "ls-files", "-z").split(b"\x00") if item]
    if not tracked:
        raise ContractError("Generator repository has no tracked files")
    tracked_names = {item.decode("utf-8") for item in tracked}
    name_audit = _audit_all_checkout_names(source_root, tracked_names)
    manifest = hashlib.sha256()
    imports: set[str] = set()
    for raw_relative in tracked:
        relative = raw_relative.decode("utf-8")
        path = source_root / relative
        if not path.is_file() or path.is_symlink():
            raise ContractError(f"Tracked path is not one regular file: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise ContractError(f"Tracked human/binary/data-like file is forbidden: {relative}")
        if path.name not in SPECIAL_NAMES and path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ContractError(f"Unexpected tracked source type: {relative}")
        payload = path.read_bytes()
        manifest.update(relative.encode("utf-8"))
        manifest.update(b"\x00")
        manifest.update(hashlib.sha256(payload).digest())
        manifest.update(b"\n")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError(f"Tracked source/document is not UTF-8 text: {relative}") from exc
        if any(token in text for token in FORBIDDEN_SOURCE_PATH_TEXT):
            raise ContractError(f"Absolute/user-local path text is forbidden: {relative}")
        if path.suffix.lower() == ".json" and any(token in text.lower() for token in FORBIDDEN_CONFIG_TEXT):
            raise ContractError(f"Clinical/human-source string is forbidden in configuration: {relative}")
        if path.suffix.lower() == ".py":
            tree = ast.parse(payload, filename=relative)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports.add(node.module.split(".", 1)[0])
    unexpected_imports = sorted(imports - ALLOWED_IMPORT_ROOTS)
    if unexpected_imports:
        raise ContractError(f"Unapproved source dependencies: {unexpected_imports!r}")
    return {
        "schema": "simple-synthetic-generator-static-audit-v1",
        "status": "passed",
        "head": head,
        "tracked_file_count": len(tracked),
        "tracked_tree_digest": manifest.hexdigest(),
        "import_roots": sorted(imports),
        "name_only_checkout_audit": name_audit,
        "source_tree_data_like_files_outside_allowlisted_venv": 0,
        "runtime_input_classes": ["tracked frozen settings JSON", "tracked complete hash-pinned lock"],
    }


def require_tracked_input(source_root: Path, path: Path, expected_prefix: str) -> None:
    try:
        relative = path.resolve(strict=True).relative_to(source_root.resolve(strict=True)).as_posix()
    except (FileNotFoundError, ValueError) as exc:
        raise ContractError("Runtime input must be a tracked regular file inside generator source") from exc
    if not relative.startswith(expected_prefix) or path.is_symlink() or not path.is_file():
        raise ContractError(f"Runtime input is outside allowlisted prefix {expected_prefix!r}")
    tracked = set(_git(source_root, "ls-files").decode("utf-8").splitlines())
    if relative not in tracked:
        raise ContractError(f"Runtime input is not tracked: {relative}")
