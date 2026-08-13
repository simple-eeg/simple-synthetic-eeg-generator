from __future__ import annotations

import tempfile
import hashlib
import json
import unittest
from pathlib import Path

from simple_synthetic_eeg_generator.environment import (
    EXPECTED_LOCK_SHA256,
    EXPECTED_PACKAGES,
    parse_lock_file,
    validate_commit,
    validate_lock_file,
)
from simple_synthetic_eeg_generator.errors import EnvironmentLockError

HASH = "a" * 64


def lock_text(packages: dict[str, str]) -> str:
    rows = ["--require-hashes", "--only-binary=:all:"]
    rows.extend(f"{name}=={version} --hash=sha256:{HASH}" for name, version in packages.items())
    return "\n".join(rows) + "\n"


class EnvironmentLockTests(unittest.TestCase):
    def test_repository_locks_are_exact_complete_19_distribution_set(self) -> None:
        root = Path(__file__).resolve().parents[1]
        producing = root / "requirements/producing.lock"
        testing = root / "requirements/test.lock"
        self.assertEqual(producing.read_bytes(), testing.read_bytes())
        self.assertEqual(producing.stat().st_size, 1846)
        self.assertEqual(
            hashlib.sha256(producing.read_bytes()).hexdigest(),
            "ed84d519fd102843c2da38e7174d829a352eabfb4babdb8321018dbb9cce6b05",
        )
        packages, _ = parse_lock_file(producing)
        self.assertEqual(len(packages), 19)
        self.assertEqual(packages, EXPECTED_PACKAGES)
        self.assertEqual(packages["python-dateutil"], "2.9.0.post0")
        self.assertEqual(validate_lock_file(producing), EXPECTED_LOCK_SHA256)

    def test_parser_requires_every_distribution_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.txt"
            path.write_text(lock_text({"numpy": "2.2.2", "pip": "25.2"}), encoding="utf-8")
            packages, digest = parse_lock_file(path)
            self.assertEqual(packages, {"numpy": "2.2.2", "pip": "25.2"})
            self.assertEqual(len(digest), 64)

    def test_parser_rejects_unhashed_url_editable_local_and_duplicate(self) -> None:
        invalid = [
            "--require-hashes\nnumpy==2.2.2\n",
            f"--require-hashes\nnumpy @ https://example.invalid/numpy.whl --hash=sha256:{HASH}\n",
            f"--require-hashes\n-e . --hash=sha256:{HASH}\n",
            f"--require-hashes\nnumpy==2.2.2 --hash=sha256:{HASH}\nnumpy==2.2.2 --hash=sha256:{HASH}\n",
        ]
        for content in invalid:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "lock.txt"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(EnvironmentLockError):
                    parse_lock_file(path)

    def test_validate_commit(self) -> None:
        expected = "1" * 40
        self.assertEqual(validate_commit(expected, "commit"), expected)
        for invalid in ("1" * 39, "A" * 40, "g" * 40):
            with self.assertRaises(EnvironmentLockError):
                validate_commit(invalid, "commit")

    def test_validate_lock_rejects_any_other_fully_hashed_package_map_or_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changed_version = root / "changed-version.lock"
            changed = dict(EXPECTED_PACKAGES)
            changed["six"] = "1.16.0"
            changed_version.write_text(lock_text(changed), encoding="utf-8")
            with self.assertRaises(EnvironmentLockError):
                validate_lock_file(changed_version)

            changed_hash = root / "changed-hash.lock"
            original = (Path(__file__).resolve().parents[1] / "requirements/producing.lock").read_text()
            changed_hash.write_text(original.replace("d002b6f0", "a002b6f0", 1), encoding="utf-8")
            with self.assertRaises(EnvironmentLockError):
                validate_lock_file(changed_hash)

    def test_interpreter_receipt_uses_role_tokens_not_local_absolute_paths(self) -> None:
        from simple_synthetic_eeg_generator.environment import validate_producing_interpreter

        root = Path(__file__).resolve().parents[1]
        if not (root / ".venv/bin/python").exists():
            self.skipTest("candidate-local locked venv is absent")
        if Path(__import__("sys").prefix) != root / ".venv":
            self.skipTest("test process is not running in the candidate-local locked venv")
        receipt = validate_producing_interpreter(root)
        encoded = json.dumps(receipt, sort_keys=True)
        self.assertNotIn(str(root), encoded)
        self.assertNotIn("/" + "Users" + "/", encoded)
        self.assertEqual(receipt["lexical_path"], ".venv/bin/python")
        self.assertEqual(receipt["sys_prefix_role"], ".venv")

    def test_interpreter_rejects_symlinked_venv_or_bin_before_entry_links(self) -> None:
        from unittest import mock
        from simple_synthetic_eeg_generator.environment import validate_producing_interpreter

        root = Path(__file__).resolve().parents[1]
        with mock.patch.object(Path, "is_symlink", autospec=True) as is_link:
            is_link.side_effect = lambda path: path == root / ".venv"
            with self.assertRaises(EnvironmentLockError):
                validate_producing_interpreter(root)
        with mock.patch.object(Path, "is_symlink", autospec=True) as is_link:
            is_link.side_effect = lambda path: path == root / ".venv" / "bin"
            with self.assertRaises(EnvironmentLockError):
                validate_producing_interpreter(root)


if __name__ == "__main__":
    unittest.main()
