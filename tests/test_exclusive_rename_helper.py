from __future__ import annotations

import ctypes
import errno
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "exclusive_rename_macos.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("exclusive_rename_macos", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load exclusive rename helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExclusiveRenameHelperTests(unittest.TestCase):
    def run_helper(self, *arguments: Path | str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", str(HELPER), *(str(item) for item in arguments)],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is macOS-only")
    def test_successfully_promotes_one_absent_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, destination = root / "partial", root / "final"
            source.mkdir()
            (source / "value.txt").write_text("accepted", encoding="utf-8")
            result = self.run_helper(source, destination)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(source.exists())
            self.assertEqual((destination / "value.txt").read_text(), "accepted")

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is macOS-only")
    def test_empty_and_nonempty_existing_destinations_are_never_overwritten(self) -> None:
        for nonempty in (False, True):
            with self.subTest(nonempty=nonempty), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                source, destination = root / "partial", root / "final"
                source.mkdir()
                (source / "source.txt").write_text("source", encoding="utf-8")
                destination.mkdir()
                if nonempty:
                    (destination / "accepted.txt").write_text("accepted", encoding="utf-8")
                result = self.run_helper(source, destination)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual((source / "source.txt").read_text(), "source")
                self.assertEqual(destination.is_dir(), True)
                if nonempty:
                    self.assertEqual((destination / "accepted.txt").read_text(), "accepted")

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is macOS-only")
    def test_symlink_source_and_destination_are_refused_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            real_source = root / "real-source"
            real_source.mkdir()
            (real_source / "source.txt").write_text("source", encoding="utf-8")
            source_link = root / "partial"
            source_link.symlink_to(real_source, target_is_directory=True)
            result = self.run_helper(source_link, root / "final")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual((real_source / "source.txt").read_text(), "source")

            source = root / "second-partial"
            source.mkdir()
            (source / "source.txt").write_text("second", encoding="utf-8")
            target = root / "existing-target"
            target.mkdir()
            destination_link = root / "second-final"
            destination_link.symlink_to(target, target_is_directory=True)
            result = self.run_helper(source, destination_link)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual((source / "source.txt").read_text(), "second")
            self.assertTrue(destination_link.is_symlink())

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is macOS-only")
    def test_nonsibling_and_wrong_argument_count_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "partial"
            other = root / "other"
            source.mkdir()
            other.mkdir()
            self.assertEqual(self.run_helper(source, other / "final").returncode, 2)
            self.assertTrue(source.is_dir())
            self.assertEqual(self.run_helper(source).returncode, 2)
            self.assertTrue(source.is_dir())

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is macOS-only")
    def test_destination_creation_race_is_exclusive_and_preserves_both(self) -> None:
        helper = load_helper()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, destination = root / "partial", root / "final"
            source.mkdir()
            (source / "source.txt").write_text("source", encoding="utf-8")

            def raced_rename(_source: bytes, _destination: bytes, _flags: int) -> int:
                destination.mkdir()
                (destination / "accepted.txt").write_text("accepted", encoding="utf-8")
                ctypes.set_errno(errno.EEXIST)
                return -1

            with self.assertRaises(SystemExit) as caught:
                helper.promote([str(source), str(destination)], renamex=raced_rename)
            self.assertEqual(caught.exception.code, 3)
            self.assertEqual((source / "source.txt").read_text(), "source")
            self.assertEqual((destination / "accepted.txt").read_text(), "accepted")


if __name__ == "__main__":
    unittest.main()
