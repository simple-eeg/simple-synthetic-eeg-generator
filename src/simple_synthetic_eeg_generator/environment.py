"""Producing-runtime and reviewed-lock gates."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import re
import sys
from pathlib import Path

from .canonical import sha256_file
from .errors import EnvironmentLockError

EXPECTED_PACKAGES = {
    "contourpy": "1.3.3",
    "cycler": "0.12.1",
    "fonttools": "4.63.0",
    "iniconfig": "2.3.0",
    "kiwisolver": "1.5.0",
    "matplotlib": "3.10.0",
    "neurodsp": "2.3.0",
    "numpy": "2.2.2",
    "packaging": "26.3",
    "pillow": "12.3.0",
    "pip": "25.2",
    "pluggy": "1.6.0",
    "pyparsing": "3.3.2",
    "pytest": "8.3.4",
    "python-dateutil": "2.9.0.post0",
    "scipy": "1.15.1",
    "setuptools": "76.0.0",
    "six": "1.17.0",
    "wheel": "0.45.1",
}
EXPECTED_LOCK_SHA256 = "ed84d519fd102843c2da38e7174d829a352eabfb4babdb8321018dbb9cce6b05"
EXPECTED_PYTHON = (3, 13, 6)
EXPECTED_MACOS = "26.6.1"
EXPECTED_MACHINE = "arm64"
EXPECTED_PYTHON_VERSION = (
    "3.13.6 (main, Aug  6 2025, 13:05:20) "
    "[Clang 17.0.0 (clang-1700.0.13.3)]"
)
EXPECTED_PYTHON_LINK = "python3.13"
EXPECTED_PYTHON313_LINK = "/opt/homebrew/opt/python@3.13/bin/python3.13"
EXPECTED_PYTHON_CANONICAL = Path(
    "/opt/homebrew/Cellar/python@3.13/3.13.6/Frameworks/Python.framework/"
    "Versions/3.13/bin/python3.13"
)
EXPECTED_PYTHON_SHA256 = "0d1fc12cf4887074b3eb257241f152cb85ca5a135879120b7e8e3b9aa57d5094"
EXPECTED_BASE_PREFIX = Path(
    "/opt/homebrew/opt/python@3.13/Frameworks/Python.framework/Versions/3.13"
)
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
LOCK_REQUIREMENT = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s\\]+)"
    r"(?:\s+--hash=sha256:[0-9a-f]{64})+\s*$"
)


def normalise_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock_file(path: Path) -> tuple[dict[str, str], str]:
    """Parse a pip-compile style lock and require a hash for every distribution."""

    if not path.is_file() or path.is_symlink():
        raise EnvironmentLockError("Lock path must be one existing regular file")
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    if "--require-hashes" not in text:
        raise EnvironmentLockError("Producing lock must enable --require-hashes")
    forbidden = ("-e ", "--editable", "file:", "git+", "http://", "https://", "../")
    if any(token in lowered for token in forbidden):
        raise EnvironmentLockError("Producing lock contains an editable/local/URL dependency")
    logical: list[str] = []
    pending = ""
    for original in text.splitlines():
        line = original.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        logical.append((pending + line).strip())
        pending = ""
    if pending:
        raise EnvironmentLockError("Producing lock ends with an incomplete continuation")
    packages: dict[str, str] = {}
    for line in logical:
        if line.startswith("--"):
            if line not in {"--require-hashes", "--only-binary=:all:"}:
                raise EnvironmentLockError(f"Unsupported global lock option: {line}")
            continue
        match = LOCK_REQUIREMENT.fullmatch(line)
        if match is None:
            raise EnvironmentLockError("Every locked distribution must be exact and SHA-256 hashed")
        name = normalise_name(match.group(1))
        if name in packages:
            raise EnvironmentLockError(f"Duplicate distribution in lock: {name}")
        packages[name] = match.group(2)
    if not packages:
        raise EnvironmentLockError("Producing lock contains no pinned distributions")
    return packages, sha256_file(path)


def validate_commit(value: str, name: str) -> str:
    if not HEX40.fullmatch(value):
        raise EnvironmentLockError(f"{name} must be a lowercase 40-hex commit")
    return value


def validate_producing_interpreter(source_root: Path) -> dict[str, str]:
    """Bind the process to the reviewed source-local venv interpreter chain."""

    lexical = source_root / ".venv" / "bin" / "python"
    intermediate = source_root / ".venv" / "bin" / "python3.13"
    expected_prefix = source_root / ".venv"
    if expected_prefix.is_symlink() or not expected_prefix.is_dir():
        raise EnvironmentLockError("Producing .venv must be one non-symlink directory")
    if (expected_prefix / "bin").is_symlink() or not (expected_prefix / "bin").is_dir():
        raise EnvironmentLockError("Producing .venv/bin must be one non-symlink directory")
    if not lexical.is_symlink() or os.readlink(lexical) != EXPECTED_PYTHON_LINK:
        raise EnvironmentLockError("Producing .venv/bin/python symlink identity differs")
    if not intermediate.is_symlink() or os.readlink(intermediate) != EXPECTED_PYTHON313_LINK:
        raise EnvironmentLockError("Producing .venv/bin/python3.13 symlink identity differs")
    try:
        canonical = lexical.resolve(strict=True)
    except FileNotFoundError as exc:
        raise EnvironmentLockError("Producing Python symlink chain is broken") from exc
    if canonical != EXPECTED_PYTHON_CANONICAL:
        raise EnvironmentLockError("Producing Python canonical target differs")
    if not canonical.is_file() or canonical.is_symlink():
        raise EnvironmentLockError("Producing Python canonical target is not one regular file")
    if sha256_file(canonical) != EXPECTED_PYTHON_SHA256:
        raise EnvironmentLockError("Producing Python executable bytes differ")
    if Path(sys.prefix) != expected_prefix:
        raise EnvironmentLockError("sys.prefix is not the audited source-root virtual environment")
    if Path(sys.base_prefix) != EXPECTED_BASE_PREFIX:
        raise EnvironmentLockError("sys.base_prefix differs from the reviewed interpreter")
    if Path(sys.executable) != lexical:
        raise EnvironmentLockError("sys.executable is not the exact lexical .venv/bin/python path")
    if sys.version != EXPECTED_PYTHON_VERSION:
        raise EnvironmentLockError("Full Python build identity differs from the reviewed interpreter")
    return {
        "lexical_path": ".venv/bin/python",
        "lexical_link_text": EXPECTED_PYTHON_LINK,
        "intermediate_path": ".venv/bin/python3.13",
        "intermediate_link_text": EXPECTED_PYTHON313_LINK,
        "canonical_target_sha256": EXPECTED_PYTHON_SHA256,
        "sys_prefix_role": ".venv",
        "sys_executable_role": ".venv/bin/python",
        "sys_version": sys.version,
    }


def validate_lock_file(path: Path) -> str:
    """Reject anything except a reviewed hash-pinned registry lock."""

    packages, digest = parse_lock_file(path)
    expected = {normalise_name(package): version for package, version in EXPECTED_PACKAGES.items()}
    if digest != EXPECTED_LOCK_SHA256:
        raise EnvironmentLockError(
            f"Producing lock SHA-256 differs from the reviewed lock: {digest}"
        )
    if packages != expected:
        raise EnvironmentLockError("Producing lock package map differs from the reviewed 19-package map")
    return digest


def producing_environment_receipt(lock_file: Path, source_root: Path) -> dict[str, object]:
    if sys.version_info[:3] != EXPECTED_PYTHON:
        raise EnvironmentLockError(
            f"Python must be exactly {'.'.join(map(str, EXPECTED_PYTHON))}, got {platform.python_version()}"
        )
    if platform.system() != "Darwin" or platform.mac_ver()[0] != EXPECTED_MACOS:
        raise EnvironmentLockError(
            f"Producing OS must be macOS {EXPECTED_MACOS}, got {platform.platform()}"
        )
    if platform.machine() != EXPECTED_MACHINE:
        raise EnvironmentLockError(
            f"Producing machine must be {EXPECTED_MACHINE}, got {platform.machine()}"
        )
    interpreter = validate_producing_interpreter(source_root)
    lock_digest = validate_lock_file(lock_file)
    locked = {normalise_name(package): version for package, version in EXPECTED_PACKAGES.items()}
    installed: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            raise EnvironmentLockError("Installed distribution has no canonical name")
        name = normalise_name(raw_name)
        if name in installed:
            raise EnvironmentLockError(f"Duplicate installed distribution: {name}")
        installed[name] = distribution.version
    if installed != locked:
        missing = sorted(set(locked) - set(installed))
        extra = sorted(set(installed) - set(locked))
        changed = sorted(name for name in set(installed) & set(locked) if installed[name] != locked[name])
        raise EnvironmentLockError(
            f"Installed distribution set differs from lock; missing={missing!r}, "
            f"extra={extra!r}, changed={changed!r}"
        )
    for package, expected in EXPECTED_PACKAGES.items():
        if installed.get(normalise_name(package)) != expected:
            raise EnvironmentLockError(f"{package} must be {expected}")
    return {
        "schema": "simple-synthetic-producing-environment-v1",
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": f"macOS {platform.mac_ver()[0]}",
        "machine": platform.machine(),
        "packages": installed,
        "lock_sha256": lock_digest,
        "distribution_count": len(installed),
        "interpreter": interpreter,
    }
