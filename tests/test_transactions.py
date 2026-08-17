from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from simple_synthetic_eeg_generator.errors import TransactionError
from simple_synthetic_eeg_generator.settings import SIMPLE_INPUT_CONTRACT, TESTED_SIMPLE_COMMIT
from simple_synthetic_eeg_generator.transaction import (
    exclusive_atomic_rename,
    refuse_stale_partials,
    require_canonical_absent_output,
)


class TransactionBoundaryTests(unittest.TestCase):
    def test_simple_compatibility_identity_is_exact(self) -> None:
        self.assertEqual(TESTED_SIMPLE_COMMIT, "e4843b858131d7d6e019740de24f44ade12bc813")
        self.assertEqual(SIMPLE_INPUT_CONTRACT, "simple-synthetic-input-v1")

    def test_stale_partial_requires_explicit_inspection_before_retry(self) -> None:
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

if __name__ == "__main__":
    unittest.main()
