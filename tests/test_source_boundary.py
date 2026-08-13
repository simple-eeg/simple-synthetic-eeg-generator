from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from simple_synthetic_eeg_generator.audit import (
    _audit_all_checkout_names,
    require_audited_module_origins,
)
from simple_synthetic_eeg_generator.cli import parser
from simple_synthetic_eeg_generator.errors import ContractError

ROOT = Path(__file__).resolve().parents[1]


class SourceBoundaryTests(unittest.TestCase):
    def test_no_alternate_background_implementation_or_real_eeg_dependency(self) -> None:
        model = (ROOT / "src/simple_synthetic_eeg_generator/model.py").read_text(encoding="utf-8")
        self.assertIn("from neurodsp.sim import set_random_seed, sim_powerlaw", model)
        self.assertEqual(model.count("sim_powerlaw("), 1)  # sole production call
        all_source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src").rglob("*.py")).lower()
        for forbidden in ("import mne", "eeglabio", "sereega", "pandas.read", "requests.get", "urlopen("):
            self.assertNotIn(forbidden, all_source)

    def test_generator_has_no_network_or_interactive_input_calls(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            tree = ast.parse(path.read_bytes(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"input", "eval", "exec"}, str(path))

    def test_gitignore_rejects_generated_workflow_types(self) -> None:
        content = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("*.set", "*.fdt", "*.f32le", "*.mat", "*.log"):
            self.assertIn(pattern, content)

    def test_production_cli_has_no_generic_manifest_traversal_command(self) -> None:
        choices = parser()._subparsers._group_actions[0].choices
        self.assertEqual(set(choices), {"validate-settings", "derive-seed", "generate"})
        self.assertNotIn("verify-manifest", (ROOT / "src/simple_synthetic_eeg_generator/cli.py").read_text())
        self.assertNotIn("[project.scripts]", (ROOT / "pyproject.toml").read_text())

    def test_isolated_launcher_ignores_shadow_package_for_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            shadow = Path(directory) / "simple_synthetic_eeg_generator"
            shadow.mkdir()
            (shadow / "__init__.py").write_text("raise RuntimeError('shadow executed')\n")
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(shadow.parent)
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ROOT / "tools/run_generator.py"),
                    "validate-settings",
                    "--settings",
                    str(ROOT / "config/generator_settings.json"),
                ],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "valid simple-synthetic-generator-settings-v1")

    def test_no_personal_or_server_paths_in_any_tracked_text(self) -> None:
        text_suffixes = {".cff", ".in", ".json", ".lock", ".m", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or ".venv" in path.parts
                or ".git" in path.parts
                or "__pycache__" in path.parts
                or (path.suffix.lower() not in text_suffixes and path.name not in {".gitignore", "LICENSE"})
            ):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/" + "Users" + "/", text, str(path))
            self.assertNotIn("/" + "Volumes" + "/", text, str(path))

    def test_name_only_audit_rejects_ignored_eeg_and_output_without_reading_contents(self) -> None:
        for relative in ("ignored.set", "outputs/report.txt"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"must-not-be-read")
                tracked: set[str] = set()
                with self.assertRaises(ContractError):
                    _audit_all_checkout_names(root, tracked)

    def test_loaded_shadow_package_is_rejected_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            shadow = Path(directory) / "simple_synthetic_eeg_generator"
            shadow.mkdir()
            (shadow / "__init__.py").write_text("__version__='0.1.0-shadow'\n")
            program = (
                "import pathlib,sys;"
                f"sys.path.insert(0,{str(shadow.parent)!r});"
                "import simple_synthetic_eeg_generator;"
                f"simple_synthetic_eeg_generator.__path__.append({str(ROOT / 'src/simple_synthetic_eeg_generator')!r});"
                "from simple_synthetic_eeg_generator.audit import require_audited_module_origins;"
                f"require_audited_module_origins(pathlib.Path({str(ROOT)!r}))"
            )
            result = subprocess.run(
                [sys.executable, "-c", program],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the exact audited source root", result.stderr)

    def test_all_current_generator_module_origins_are_audited_py_sources(self) -> None:
        origins = require_audited_module_origins(ROOT)
        self.assertIn("simple_synthetic_eeg_generator", origins)
        self.assertTrue(all(relative.endswith(".py") for relative in origins.values()))


if __name__ == "__main__":
    unittest.main()
