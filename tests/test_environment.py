from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from simple_synthetic_eeg_generator import environment
from simple_synthetic_eeg_generator.platform_support import venv_python
from simple_synthetic_eeg_generator.environment import (
    CAPABILITY_PROBE_TIMEOUT_SECONDS,
    RUNTIME_PACKAGES,
    _validate_scientific_python_capabilities,
    runtime_environment_receipt,
    validate_project_interpreter,
)
from simple_synthetic_eeg_generator.errors import EnvironmentCapabilityError


class EnvironmentCapabilityTests(unittest.TestCase):
    def test_current_checkout_runtime_passes_and_receipt_shape_is_exact(self) -> None:
        root = Path(__file__).resolve().parents[1]
        if Path(__import__("sys").prefix) != root / ".venv":
            self.skipTest("test process is not running in the checkout-local virtual environment")
        receipt = runtime_environment_receipt(root)
        self.assertEqual(
            set(receipt),
            {
                "schema",
                "python_version",
                "python_implementation",
                "operating_system",
                "operating_system_release",
                "machine",
                "packages",
            },
        )
        self.assertEqual(receipt["schema"], "simple-synthetic-python-runtime-v1")
        self.assertEqual(set(receipt["packages"]), set(RUNTIME_PACKAGES))
        self.assertNotIn("/" + "Users" + "/", repr(receipt))

    def test_newer_versions_architecture_and_extra_installed_packages_are_not_gates(self) -> None:
        versions = {
            "matplotlib": "9.1",
            "neurodsp": "7.2",
            "numpy": "8.3",
            "scipy": "6.4",
        }
        with mock.patch.object(environment, "validate_project_interpreter"), mock.patch.object(
            environment, "_validate_scientific_python_capabilities"
        ), mock.patch.object(environment.platform, "system", return_value="Darwin"), mock.patch.object(
            environment.platform, "mac_ver", return_value=("99.4", ("", "", ""), "")
        ), mock.patch.object(environment.platform, "machine", return_value="x86_64"), mock.patch.object(
            environment.platform, "python_version", return_value="3.15.2"
        ), mock.patch.object(
            environment.platform, "python_implementation", return_value="CPython"
        ), mock.patch.object(
            environment.importlib.metadata, "version", side_effect=lambda name: versions[name]
        ):
            receipt = runtime_environment_receipt(Path("/unused"))
        self.assertEqual(receipt["python_version"], "3.15.2")
        self.assertEqual(receipt["operating_system_release"], "99.4")
        self.assertEqual(receipt["machine"], "x86_64")
        self.assertEqual(receipt["packages"], versions)

    def test_missing_required_distribution_fails(self) -> None:
        def version(name: str) -> str:
            if name == "numpy":
                raise environment.importlib.metadata.PackageNotFoundError(name)
            return "1"

        with mock.patch.object(environment, "validate_project_interpreter"), mock.patch.object(
            environment.platform, "system", return_value="Darwin"
        ), mock.patch.object(environment.importlib.metadata, "version", side_effect=version):
            with self.assertRaises(EnvironmentCapabilityError):
                runtime_environment_receipt(Path("/unused"))

    def test_capability_probe_uses_selected_interpreter_in_isolated_mode(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch.object(environment.subprocess, "run", return_value=completed) as run:
            _validate_scientific_python_capabilities()
        arguments, keywords = run.call_args
        self.assertEqual(arguments[0][:2], [environment.sys.executable, "-I"])
        self.assertEqual(keywords["timeout"], CAPABILITY_PROBE_TIMEOUT_SECONDS)
        self.assertNotIn("PYTHONHOME", keywords["env"])
        self.assertNotIn("PYTHONPATH", keywords["env"])
        self.assertIn("MPLCONFIGDIR", keywords["env"])

    def test_capability_probe_translates_start_and_stall_failures(self) -> None:
        failures = (
            OSError("cannot start"),
            environment.subprocess.TimeoutExpired([environment.sys.executable], 180),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), mock.patch.object(
                environment.subprocess, "run", side_effect=failure
            ), self.assertRaises(EnvironmentCapabilityError):
                _validate_scientific_python_capabilities()

    def test_unsupported_runtime_fails_before_generation(self) -> None:
        with mock.patch.object(environment.platform, "system", return_value="UnknownOS"):
            with self.assertRaises(EnvironmentCapabilityError):
                runtime_environment_receipt(Path("/unused"))

    def test_project_venv_accepts_regular_or_arbitrarily_targeted_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binary = venv_python(root).parent
            binary.mkdir(parents=True)
            python = venv_python(root)
            python.write_bytes(b"interpreter")
            python.chmod(0o755)
            with mock.patch.object(environment.sys, "prefix", str(root / ".venv")), mock.patch.object(
                environment.sys, "executable", str(python)
            ), mock.patch.object(environment.sys, "version_info", (3, 14, 0)):
                validate_project_interpreter(root)

            python.unlink()
            external = root / "python-target"
            external.write_bytes(b"interpreter")
            external.chmod(0o755)
            python.symlink_to(external)
            with mock.patch.object(environment.sys, "prefix", str(root / ".venv")), mock.patch.object(
                environment.sys, "executable", str(python)
            ), mock.patch.object(environment.sys, "version_info", (3, 14, 0)):
                validate_project_interpreter(root)

    def test_project_venv_rejects_wrong_prefix_and_old_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binary = venv_python(root).parent
            binary.mkdir(parents=True)
            python = venv_python(root)
            python.write_bytes(b"interpreter")
            python.chmod(0o755)
            with mock.patch.object(environment.sys, "prefix", "/wrong"), mock.patch.object(
                environment.sys, "executable", str(python)
            ):
                with self.assertRaises(EnvironmentCapabilityError):
                    validate_project_interpreter(root)
            with mock.patch.object(environment.sys, "prefix", str(root / ".venv")), mock.patch.object(
                environment.sys, "executable", str(python)
            ), mock.patch.object(environment.sys, "version_info", (3, 9, 99)):
                with self.assertRaises(EnvironmentCapabilityError):
                    validate_project_interpreter(root)

if __name__ == "__main__":
    unittest.main()
