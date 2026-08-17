"""Capability checks and path-free provenance for the Python runtime."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from .errors import EnvironmentCapabilityError

MINIMUM_PYTHON = (3, 10)
RUNTIME_PACKAGES = ("matplotlib", "neurodsp", "numpy", "scipy")
CAPABILITY_PROBE_TIMEOUT_SECONDS = 180


def validate_project_interpreter(source_root: Path) -> None:
    """Require this checkout's virtual environment without pinning its target."""

    virtual_environment = source_root / ".venv"
    binary_directory = virtual_environment / "bin"
    interpreter = binary_directory / "python"
    if virtual_environment.is_symlink() or not virtual_environment.is_dir():
        raise EnvironmentCapabilityError(
            "The checkout-local .venv is absent or is a symlink; recreate it as described in README.md"
        )
    if binary_directory.is_symlink() or not binary_directory.is_dir():
        raise EnvironmentCapabilityError("The checkout-local .venv/bin directory is invalid")
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise EnvironmentCapabilityError("The checkout-local .venv/bin/python is not executable")
    try:
        resolved_interpreter = interpreter.resolve(strict=True)
    except OSError as exc:
        raise EnvironmentCapabilityError("The checkout-local Python interpreter cannot be resolved") from exc
    if not resolved_interpreter.is_file():
        raise EnvironmentCapabilityError("The checkout-local Python target is not a regular file")
    if Path(sys.prefix) != virtual_environment:
        raise EnvironmentCapabilityError("Python is not running from this checkout's .venv")
    if Path(sys.executable) != interpreter:
        raise EnvironmentCapabilityError("Python was not launched as this checkout's .venv/bin/python")
    if sys.version_info[:2] < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        raise EnvironmentCapabilityError(
            f"Python {required} or newer is required; found {platform.python_version()}"
        )


def _validate_scientific_python_capabilities() -> None:
    """Check required APIs without changing the producing process's import state."""

    probe = """
import matplotlib
import numpy as np
from neurodsp.sim import set_random_seed, sim_powerlaw
from scipy.signal import periodogram, welch
from scipy.signal.windows import tukey

capabilities = (
    np.random.PCG64DXSM,
    np.trapezoid,
    periodogram,
    welch,
    tukey,
    set_random_seed,
    sim_powerlaw,
)
if not all(callable(capability) for capability in capabilities):
    raise RuntimeError("a required scientific API is not callable")
"""
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix=".simple-synth-capabilities-") as directory:
        environment["MPLCONFIGDIR"] = directory
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-c", probe],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
                timeout=CAPABILITY_PROBE_TIMEOUT_SECONDS,
            )
        except OSError as exc:
            raise EnvironmentCapabilityError(
                "The selected Python interpreter could not run the scientific capability probe"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise EnvironmentCapabilityError(
                "The scientific capability probe stalled for three minutes; "
                "check the checkout's Python installation before retrying"
            ) from exc
    if result.returncode != 0:
        raise EnvironmentCapabilityError(
            "The Python environment does not provide the required scientific capabilities"
        )


def runtime_environment_receipt(source_root: Path) -> dict[str, object]:
    """Validate capabilities and record the actual path-free producing runtime."""

    if platform.system() != "Darwin":
        raise EnvironmentCapabilityError(
            "Dataset publication currently requires macOS for exclusive no-overwrite promotion"
        )
    validate_project_interpreter(source_root)
    packages: dict[str, str] = {}
    for name in RUNTIME_PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise EnvironmentCapabilityError(f"Required Python package is not installed: {name}") from exc
    _validate_scientific_python_capabilities()
    return {
        "schema": "simple-synthetic-python-runtime-v1",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "operating_system": "macOS",
        "operating_system_release": platform.mac_ver()[0],
        "machine": platform.machine(),
        "packages": packages,
    }
