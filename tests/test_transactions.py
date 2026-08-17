from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from simple_synthetic_eeg_generator.errors import TransactionError, ValidationError
from simple_synthetic_eeg_generator.reproducibility import (
    _compare_exact,
    _finalise_reproducible_runs,
    _sanitise_worker_diagnostic,
    _sanitised_worker_environment,
)
from simple_synthetic_eeg_generator.settings import SIMPLE_FRAMEWORK_COMMIT
from simple_synthetic_eeg_generator.transaction import (
    exclusive_atomic_rename,
    refuse_stale_partials,
    require_canonical_absent_output,
)


class TransactionBoundaryTests(unittest.TestCase):
    def test_sanitised_worker_environment_drops_import_injection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            old = {name: os.environ.get(name) for name in ("PYTHONPATH", "HOME", "TMPDIR")}
            os.environ.update(
                {"PYTHONPATH": "/malicious/shadow", "HOME": "/hostile/home", "TMPDIR": "/hostile/tmp"}
            )
            try:
                environment = _sanitised_worker_environment(root, root / "worker-environment")
            finally:
                for name, value in old.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
            self.assertNotIn("PYTHONPATH", environment)
            self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertEqual(environment["SIMPLE_SYNTH_AUDITED_SOURCE_ROOT"], str(root))
            for name, relative in (
                ("HOME", "home"), ("TMPDIR", "tmp"), ("MPLCONFIGDIR", "mplconfig"),
                ("XDG_CACHE_HOME", "xdg-cache"),
            ):
                self.assertEqual(environment[name], str(root / "worker-environment" / relative))
                self.assertTrue(Path(environment[name]).is_dir())

    def test_framework_commit_literal_is_exact(self) -> None:
        self.assertEqual(SIMPLE_FRAMEWORK_COMMIT, "7fd6837587753ee8db4bf81bba238d0a3ffd44b8")

    def test_worker_diagnostic_is_bounded_and_removes_private_paths(self) -> None:
        root = Path("/private/tmp/audited-generator")
        private_prefix = "/" + "Users" + "/"
        payload = (
            f"failure in {root}/src/module.py and {private_prefix}example/secret/file.set "
            + "x" * 1000
        ).encode()
        diagnostic = _sanitise_worker_diagnostic(payload, root)
        self.assertLessEqual(len(diagnostic), 600)
        self.assertNotIn(str(root), diagnostic)
        self.assertNotIn(private_prefix, diagnostic)
        self.assertNotIn("file.set", diagnostic)
        self.assertIn("<generator-root>", diagnostic)

    def test_stale_partial_forbids_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "candidate"
            (root / "candidate.partial.prior-failure").mkdir()
            with self.assertRaises(TransactionError):
                refuse_stale_partials(output)

    def test_output_requires_canonical_non_symlink_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            require_canonical_absent_output(root / "new-output")
            alias = root / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(TransactionError):
                require_canonical_absent_output(alias / "new-output")
            with self.assertRaises(TransactionError):
                require_canonical_absent_output(root / "missing-parent" / "new-output")

    def test_exclusive_atomic_directory_promotion_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.partial"
            first.mkdir()
            (first / "value.txt").write_text("accepted", encoding="utf-8")
            destination = root / "final"
            exclusive_atomic_rename(first, destination)
            self.assertEqual((destination / "value.txt").read_text(encoding="utf-8"), "accepted")
            second = root / "second.partial"
            second.mkdir()
            (second / "value.txt").write_text("must-not-overwrite", encoding="utf-8")
            with self.assertRaises(TransactionError):
                exclusive_atomic_rename(second, destination)
            self.assertEqual((destination / "value.txt").read_text(encoding="utf-8"), "accepted")
            self.assertTrue(second.is_dir())

    def test_exact_build_comparison_detects_file_set_and_byte_difference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            (left / "a.txt").write_bytes(b"same\n")
            (right / "a.txt").write_bytes(b"same\n")
            _compare_exact(left, right)
            (right / "a.txt").write_bytes(b"different\n")
            with self.assertRaises(ValidationError):
                _compare_exact(left, right)
            (right / "a.txt").write_bytes(b"same\n")
            (right / "extra.txt").write_bytes(b"extra\n")
            with self.assertRaises(ValidationError):
                _compare_exact(left, right)

    def test_cleanup_failure_occurs_before_any_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "final"
            token = "0" * 24
            runs = [
                root / f"final.partial.{token}.{label}"
                for label in ("canonical-1", "canonical-2", "shuffled-1")
            ]
            control = root / f"final.partial.{token}.control"
            for path in [*runs, control]:
                path.mkdir()
            original_rmtree = __import__("shutil").rmtree

            def failing_cleanup(path: Path) -> None:
                if Path(path) == runs[1]:
                    raise OSError("injected cleanup failure")
                original_rmtree(path)

            with mock.patch(
                "simple_synthetic_eeg_generator.reproducibility.shutil.rmtree",
                side_effect=failing_cleanup,
            ), self.assertRaises(OSError):
                _finalise_reproducible_runs(
                    output=output, runs=runs, control=control, token=token
                )
            self.assertFalse(output.exists())
            self.assertTrue(runs[0].is_dir())


if __name__ == "__main__":
    unittest.main()
