from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import simple_synthetic_eeg_generator.user_workflow as workflow
from simple_synthetic_eeg_generator.canonical import build_manifest
from simple_synthetic_eeg_generator.errors import TransactionError, ValidationError
from simple_synthetic_eeg_generator.settings import EXPECTED_SUBJECTS, load_settings
from simple_synthetic_eeg_generator.user_workflow import (
    FINAL_NAME,
    BuildPaths,
    RuntimePaths,
    _default_reauditor,
    _matlab_environment,
    _run_child,
    orchestrate_build,
    parser,
    validate_packaged_stage,
    validate_parent,
    validate_transfer_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def make_dataset_list(path: Path) -> None:
    rows = ["subjectID,sessionID,runID,path_raw,EEGfile_raw"]
    rows.extend(
        f"{subject},01,01,data/raw/sub-{subject}/ses-01/eeg,"
        f"sub-{subject}_ses-01_run-01_eeg.set"
        for subject in EXPECTED_SUBJECTS
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")


def make_raw(raw_root: Path) -> None:
    for subject in EXPECTED_SUBJECTS:
        path = raw_root / (
            f"sub-{subject}/ses-01/eeg/sub-{subject}_ses-01_run-01_eeg.set"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic-set-{subject}\n".encode())


def make_packaged(root: Path) -> None:
    make_dataset_list(root / "data_lists" / "dataset_list.csv")
    make_raw(root / "data" / "raw")
    (root / "provenance").mkdir()
    (root / "provenance" / "internal-receipt.json").write_text("{}\n")
    (root / "MANIFEST.sha256").write_bytes(build_manifest(root))


def make_transfer(root: Path) -> None:
    make_dataset_list(root / "dataset_list.csv")
    make_raw(root / "raw")


def make_paths(parent: Path, token: str) -> BuildPaths:
    array_workspace = parent / f".{FINAL_NAME}.array-{token}"
    packaging_workspace = parent / f".{FINAL_NAME}.package-{token}"
    return BuildPaths(
        parent=parent,
        final=parent / FINAL_NAME,
        array_workspace=array_workspace,
        packaging_workspace=packaging_workspace,
        array_stage=array_workspace / "stage",
        packaged_stage=packaging_workspace / "bundle",
        transfer_partial=parent / f".{FINAL_NAME}.transfer-{token}",
    )


def make_runtime() -> RuntimePaths:
    return RuntimePaths(
        source_root=ROOT,
        python=ROOT / ".venv/bin/python",
        matlab=Path("/Applications/MATLAB_R2026a.app/bin/matlab"),
        eeglab_root=Path.home() / "Documents/MATLAB/eeglab2026.0.0",
        settings=ROOT / "config/generator_settings.json",
        lock_file=ROOT / "requirements/producing.lock",
        generator_head="a" * 40,
    )


class UserWorkflowTests(unittest.TestCase):
    def test_root_launcher_is_executable_and_exposes_one_positional_choice(self) -> None:
        launcher = ROOT / "generate_dataset"
        self.assertTrue(os.access(launcher, os.X_OK))
        arguments = parser().parse_args(["/tmp"])
        self.assertEqual(arguments.parent_directory, Path("/tmp"))
        actions = [action for action in parser()._actions if action.dest != "help"]
        self.assertEqual([action.dest for action in actions], ["parent_directory"])
        launcher_text = launcher.read_text(encoding="utf-8")
        self.assertIn("./generate_dataset", launcher_text)
        self.assertIn("[ ! -x", launcher_text)
        self.assertIn("-u -I", launcher_text)

    def test_parent_must_be_absolute_absent_writable_and_outside_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            self.assertEqual(validate_parent(parent), parent)
            with self.assertRaises(TransactionError):
                validate_parent(Path("relative"))
            (parent / FINAL_NAME).mkdir()
            with self.assertRaises(TransactionError):
                validate_parent(parent)

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            with mock.patch(
                "simple_synthetic_eeg_generator.user_workflow._has_git_boundary",
                return_value=True,
            ), self.assertRaises(TransactionError):
                validate_parent(parent)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / ".git").mkdir()
            nested = root / "nested"
            nested.mkdir()
            with self.assertRaises(TransactionError):
                validate_parent(nested)

    def test_transfer_validator_accepts_only_exact_two_entry_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "transfer"
            root.mkdir()
            make_transfer(root)
            validate_transfer_bundle(root)

            (root / "README.md").write_text("not allowed\n")
            with self.assertRaises(ValidationError):
                validate_transfer_bundle(root)

    def test_packaged_manifest_detects_source_mutation_before_transfer_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            root.mkdir()
            make_packaged(root)
            validate_packaged_stage(root)
            path = root / "data/raw/sub-031/ses-01/eeg/sub-031_ses-01_run-01_eeg.set"
            path.write_bytes(path.read_bytes() + b"mutation")
            with self.assertRaises(ValidationError):
                validate_packaged_stage(root)

    def test_transfer_validator_rejects_missing_extra_fdt_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for case in ("missing", "fdt", "symlink", "bad-list"):
                with self.subTest(case=case):
                    root = base / case
                    root.mkdir()
                    make_transfer(root)
                    subject_set = root / "raw/sub-001/ses-01/eeg/sub-001_ses-01_run-01_eeg.set"
                    if case == "missing":
                        subject_set.unlink()
                    elif case == "fdt":
                        (subject_set.parent / "external.FDT").write_bytes(b"forbidden")
                    elif case == "symlink":
                        subject_set.unlink()
                        subject_set.symlink_to(root / "dataset_list.csv")
                    else:
                        text = (root / "dataset_list.csv").read_text()
                        (root / "dataset_list.csv").write_text(
                            text.replace("data/raw/sub-001", "raw/sub-001", 1),
                            newline="",
                        )
                    with self.assertRaises(ValidationError):
                        validate_transfer_bundle(root)

    def test_transfer_validator_rejects_semantically_equal_noncanonical_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "transfer"
            root.mkdir()
            make_transfer(root)
            path = root / "dataset_list.csv"
            path.write_text(path.read_text().replace("001,01,01", '"001",01,01', 1), newline="")
            with self.assertRaises(ValidationError):
                validate_transfer_bundle(root)

    def test_orchestration_publishes_only_transfer_after_removing_rich_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            paths = make_paths(parent, "testtoken")
            runtime = make_runtime()
            settings = load_settings(runtime.settings)
            final_validation_seen = [False]

            def stage_builder(output, _runtime, _settings):
                output.mkdir()
                (output / "internal-array.f32le").write_bytes(b"internal")

            def packager(input_root, output_root, _runtime):
                self.assertTrue(input_root.is_dir())
                output_root.mkdir()
                make_packaged(output_root)

            def promoter(source, destination):
                self.assertFalse(paths.array_workspace.exists())
                self.assertFalse(paths.packaging_workspace.exists())
                self.assertTrue(paths.transfer_partial.is_dir())
                self.assertTrue(final_validation_seen[0])
                os.rename(source, destination)

            old_umask = os.umask(0o077)
            try:
                with mock.patch(
                    "simple_synthetic_eeg_generator.user_workflow.validate_packaged_stage",
                    wraps=workflow.validate_packaged_stage,
                ) as packaged_validator, mock.patch(
                    "simple_synthetic_eeg_generator.user_workflow._fsync_directory",
                    wraps=workflow._fsync_directory,
                ) as parent_sync:
                    original_transfer_validator = workflow.validate_transfer_bundle

                    def tracked_transfer_validation(root):
                        original_transfer_validator(root)
                        if not paths.array_workspace.exists() and not paths.packaging_workspace.exists():
                            final_validation_seen[0] = True

                    with mock.patch(
                        "simple_synthetic_eeg_generator.user_workflow.validate_transfer_bundle",
                        side_effect=tracked_transfer_validation,
                    ):
                        result = orchestrate_build(
                            paths=paths,
                            runtime=runtime,
                            settings=settings,
                            stage_builder=stage_builder,
                            packager=packager,
                            promoter=promoter,
                            reauditor=lambda _runtime: None,
                        )
                    self.assertEqual(packaged_validator.call_count, 2)
                    self.assertEqual(parent_sync.call_count, 1)
            finally:
                os.umask(old_umask)
            self.assertEqual(result, paths.final)
            validate_transfer_bundle(result)
            self.assertEqual({entry.name for entry in result.iterdir()}, {"dataset_list.csv", "raw"})
            self.assertEqual(result.stat().st_mode & 0o777, 0o755)
            self.assertTrue(
                all(
                    path.stat().st_mode & 0o777 == (0o755 if path.is_dir() else 0o644)
                    for path in result.rglob("*")
                )
            )
            self.assertFalse(paths.array_workspace.exists())
            self.assertFalse(paths.packaging_workspace.exists())
            self.assertFalse(paths.transfer_partial.exists())

    def test_failure_cleans_only_this_invocations_unique_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            unrelated = parent / f".{FINAL_NAME}.array-unrelated"
            unrelated.mkdir()
            paths = make_paths(parent, "failuretoken")
            runtime = make_runtime()
            settings = load_settings(runtime.settings)

            def stage_builder(output, _runtime, _settings):
                output.mkdir()

            def failing_packager(_input, output, _runtime):
                partial = output.with_name(output.name + ".partial.native")
                partial.mkdir()
                (partial / "failure.txt").write_text("failed\n")
                raise ValidationError("deliberate package failure")

            with self.assertRaises(ValidationError):
                orchestrate_build(
                    paths=paths,
                    runtime=runtime,
                    settings=settings,
                    stage_builder=stage_builder,
                    packager=failing_packager,
                    reauditor=lambda _runtime: None,
                )
            self.assertTrue(unrelated.is_dir())
            self.assertFalse(paths.array_workspace.exists())
            self.assertFalse(paths.packaging_workspace.exists())
            self.assertFalse(paths.transfer_partial.exists())
            self.assertFalse(paths.final.exists())

    def test_racer_created_selected_root_is_never_treated_as_owned(self) -> None:
        for selected in ("array_workspace", "packaging_workspace", "transfer_partial"):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory).resolve()
                paths = make_paths(parent, f"race-{selected}")
                runtime = make_runtime()
                settings = load_settings(runtime.settings)
                target = getattr(paths, selected)
                real_mkdir = os.mkdir
                raced = [False]

                def racing_mkdir(path, mode=0o777, *, dir_fd=None):
                    candidate = Path(path)
                    if candidate == target and not raced[0]:
                        real_mkdir(path, mode, dir_fd=dir_fd)
                        (target / "racer-owned.txt").write_text("preserve me\n")
                        raced[0] = True
                        raise FileExistsError("racer won exclusive creation")
                    return real_mkdir(path, mode, dir_fd=dir_fd)

                def stage_builder(output, _runtime, _settings):
                    output.mkdir()

                def packager(_input, output, _runtime):
                    output.mkdir()
                    make_packaged(output)

                with mock.patch(
                    "simple_synthetic_eeg_generator.user_workflow.os.mkdir",
                    side_effect=racing_mkdir,
                ), self.assertRaises(FileExistsError):
                    orchestrate_build(
                        paths=paths,
                        runtime=runtime,
                        settings=settings,
                        stage_builder=stage_builder,
                        packager=packager,
                        reauditor=lambda _runtime: None,
                    )
                self.assertTrue(raced[0])
                self.assertEqual((target / "racer-owned.txt").read_text(), "preserve me\n")
                self.assertFalse(paths.final.exists())

    def test_promotion_race_is_never_overwritten_or_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            paths = make_paths(parent, "racetoken")
            runtime = make_runtime()
            settings = load_settings(runtime.settings)

            def stage_builder(output, _runtime, _settings):
                output.mkdir()

            def packager(_input, output, _runtime):
                output.mkdir()
                make_packaged(output)

            def racing_promoter(_source, destination):
                destination.mkdir()
                (destination / "owner.txt").write_text("other process\n")
                raise TransactionError("destination appeared")

            with self.assertRaises(TransactionError):
                orchestrate_build(
                    paths=paths,
                    runtime=runtime,
                    settings=settings,
                    stage_builder=stage_builder,
                    packager=packager,
                    promoter=racing_promoter,
                    reauditor=lambda _runtime: None,
                )
            self.assertEqual((paths.final / "owner.txt").read_text(), "other process\n")
            self.assertFalse(paths.array_workspace.exists())
            self.assertFalse(paths.packaging_workspace.exists())
            self.assertFalse(paths.transfer_partial.exists())

    def test_matlab_environment_overrides_all_user_configuration(self) -> None:
        runtime = make_runtime()
        with mock.patch.dict(
            os.environ,
            {
                "SIMPLE_SYNTH_INPUT_ROOT": "wrong",
                "MATLABPATH": "wrong",
                "PYTHONPATH": "wrong",
                "KEEP_ME": "yes",
            },
            clear=True,
        ):
            environment = _matlab_environment(runtime, Path("/input"), Path("/output"))
        self.assertEqual(environment["SIMPLE_SYNTH_INPUT_ROOT"], "/input")
        self.assertEqual(environment["SIMPLE_SYNTH_OUTPUT_ROOT"], "/output")
        self.assertEqual(environment["KEEP_ME"], "yes")
        self.assertNotIn("MATLABPATH", environment)
        self.assertNotIn("PYTHONPATH", environment)

    def test_build_dataset_has_no_output_or_fallible_work_after_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            runtime = make_runtime()
            paths = make_paths(parent, "terminal-promotion")
            promoted = [False]

            def fake_orchestrate(**_kwargs):
                promoted[0] = True
                return paths.final

            def guarded_print(*_args, **_kwargs):
                if promoted[0]:
                    raise BrokenPipeError("output attempted after promotion")

            with mock.patch(
                "simple_synthetic_eeg_generator.user_workflow.validate_parent",
                return_value=parent,
            ), mock.patch(
                "simple_synthetic_eeg_generator.user_workflow.discover_runtime",
                return_value=runtime,
            ), mock.patch(
                "simple_synthetic_eeg_generator.user_workflow._unique_build_paths",
                return_value=paths,
            ), mock.patch(
                "simple_synthetic_eeg_generator.user_workflow.orchestrate_build",
                side_effect=fake_orchestrate,
            ), mock.patch("builtins.print", side_effect=guarded_print):
                result = workflow.build_dataset(
                    parent,
                    ROOT,
                    native_preflight=lambda _runtime: None,
                )
            self.assertTrue(promoted[0])
            self.assertEqual(result, paths.final)

    def test_post_matlab_reaudit_requires_same_clean_generator_head(self) -> None:
        runtime = make_runtime()
        with mock.patch(
            "simple_synthetic_eeg_generator.user_workflow.audit_checkout",
            return_value={"head": "b" * 40},
        ), mock.patch(
            "simple_synthetic_eeg_generator.user_workflow.require_audited_module_origins"
        ), mock.patch(
            "simple_synthetic_eeg_generator.user_workflow.validate_lock_file"
        ), mock.patch(
            "simple_synthetic_eeg_generator.user_workflow.validate_producing_interpreter"
        ), self.assertRaises(TransactionError):
            _default_reauditor(runtime)

    def test_interruption_terminates_and_waits_for_matlab_process_group(self) -> None:
        process = mock.Mock()
        process.pid = 424242
        process.poll.return_value = None
        process.wait.side_effect = [KeyboardInterrupt(), 0]
        with mock.patch(
            "simple_synthetic_eeg_generator.user_workflow.subprocess.Popen",
            return_value=process,
        ), mock.patch(
            "simple_synthetic_eeg_generator.user_workflow.os.killpg"
        ) as kill_group, self.assertRaises(KeyboardInterrupt):
            _run_child(["matlab"], cwd=ROOT, environment={})
        kill_group.assert_called_once_with(process.pid, __import__("signal").SIGTERM)
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
