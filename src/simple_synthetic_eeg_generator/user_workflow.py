"""One-choice, fail-closed build of the disposable framework transfer dataset."""

from __future__ import annotations

import argparse
import os
import secrets
import signal
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .audit import audit_checkout, require_audited_module_origins
from .canonical import (
    canonical_csv_bytes,
    sha256_file,
    verify_manifest,
    write_new_bytes,
)
from .environment import validate_lock_file, validate_producing_interpreter
from .errors import GeneratorError, TransactionError, ValidationError
from .reproducibility import generate_reproducibly
from .settings import EXPECTED_SUBJECTS, SIMPLE_FRAMEWORK_COMMIT, FrozenSettings, load_settings
from .transaction import exclusive_atomic_rename

FINAL_NAME = "simple-synthetic-eeg-demo"
MATLAB_APPLICATION = Path("/Applications/MATLAB_R2026a.app")
EEGLAB_DIRECTORY_NAME = "eeglab2026.0.0"
DATASET_LIST_HEADER = ("subjectID", "sessionID", "runID", "path_raw", "EEGfile_raw")


@dataclass(frozen=True)
class RuntimePaths:
    source_root: Path
    python: Path
    matlab: Path
    eeglab_root: Path
    settings: Path
    lock_file: Path
    generator_head: str


@dataclass(frozen=True)
class BuildPaths:
    parent: Path
    final: Path
    array_workspace: Path
    packaging_workspace: Path
    array_stage: Path
    packaged_stage: Path
    transfer_partial: Path


StageBuilder = Callable[[Path, RuntimePaths, FrozenSettings], None]
Packager = Callable[[Path, Path, RuntimePaths], None]
Promoter = Callable[[Path, Path], None]
Reauditor = Callable[[RuntimePaths], None]
NativePreflight = Callable[[RuntimePaths], None]


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        prog="./generate_dataset",
        description=(
            "Create the fixed SIMPLE synthetic dataset in "
            "<existing-parent-directory>/simple-synthetic-eeg-demo"
        ),
    )
    command.add_argument(
        "parent_directory",
        type=Path,
        help="existing parent directory in which the fixed output folder will be created",
    )
    return command


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _require_canonical_directory(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise TransactionError(f"{label} must be an absolute path")
    if path.is_symlink() or not path.is_dir():
        raise TransactionError(f"{label} must be one existing non-symlink directory")
    try:
        canonical = path.resolve(strict=True)
    except OSError as exc:
        raise TransactionError(f"{label} cannot be resolved") from exc
    if canonical != path:
        raise TransactionError(f"{label} and all its components must be canonical non-symlinks")
    return path


def _has_git_boundary(path: Path) -> bool:
    """Reject worktrees, Git directories, bare repositories, and `.git` ancestors."""

    for ancestor in (path, *path.parents):
        if _lexists(ancestor / ".git"):
            return True
    try:
        completed = subprocess.run(
            [
                "/usr/bin/git",
                "-C",
                str(path),
                "rev-parse",
                "--is-inside-work-tree",
                "--is-inside-git-dir",
                "--is-bare-repository",
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransactionError("Could not verify that the destination is outside Git") from exc
    if completed.returncode != 0:
        return False
    return any(value == "true" for value in completed.stdout.splitlines())


def validate_parent(parent: Path) -> Path:
    """Validate the user's sole choice before any build path is created."""

    parent = _require_canonical_directory(parent, "Output parent")
    if _has_git_boundary(parent):
        raise TransactionError("Output parent must be outside every Git worktree or repository")
    if not os.access(parent, os.W_OK | os.X_OK):
        raise TransactionError("Output parent is not writable")
    final = parent / FINAL_NAME
    if _lexists(final):
        raise TransactionError(
            f"{FINAL_NAME} already exists; move or delete it explicitly before generating again"
        )
    return parent


def discover_runtime(source_root: Path, *, home: Path | None = None) -> RuntimePaths:
    """Locate fixed, pre-installed dependencies without installing or configuring them."""

    source_root = _require_canonical_directory(source_root, "Generator checkout")
    python = source_root / ".venv" / "bin" / "python"
    matlab_application = _require_canonical_directory(MATLAB_APPLICATION, "MATLAB R2026a application")
    matlab = matlab_application / "bin" / "matlab"
    if matlab.is_symlink() or not matlab.is_file() or not os.access(matlab, os.X_OK):
        raise TransactionError("Exact MATLAB R2026a executable is absent or not executable")
    eeglab_root = (Path.home() if home is None else home) / "Documents" / "MATLAB" / EEGLAB_DIRECTORY_NAME
    eeglab_root = _require_canonical_directory(eeglab_root, "EEGLAB 2026.0.0 installation")
    settings = source_root / "config" / "generator_settings.json"
    lock_file = source_root / "requirements" / "producing.lock"
    audit = audit_checkout(source_root)
    require_audited_module_origins(source_root)
    validate_lock_file(lock_file)
    validate_producing_interpreter(source_root)
    return RuntimePaths(
        source_root=source_root,
        python=python,
        matlab=matlab,
        eeglab_root=eeglab_root,
        settings=settings,
        lock_file=lock_file,
        generator_head=str(audit["head"]),
    )


def _unique_build_paths(parent: Path) -> BuildPaths:
    for _ in range(10):
        token = secrets.token_hex(12)
        array_workspace = parent / f".{FINAL_NAME}.array-{token}"
        packaging_workspace = parent / f".{FINAL_NAME}.package-{token}"
        transfer_partial = parent / f".{FINAL_NAME}.transfer-{token}"
        if not any(
            _lexists(path)
            for path in (array_workspace, packaging_workspace, transfer_partial)
        ):
            return BuildPaths(
                parent=parent,
                final=parent / FINAL_NAME,
                array_workspace=array_workspace,
                packaging_workspace=packaging_workspace,
                array_stage=array_workspace / "stage",
                packaged_stage=packaging_workspace / "bundle",
                transfer_partial=transfer_partial,
            )
    raise TransactionError("Could not reserve a unique hidden build identity")


def _default_stage_builder(output: Path, runtime: RuntimePaths, settings: FrozenSettings) -> None:
    generate_reproducibly(
        output=output,
        settings=settings,
        lock_file=runtime.lock_file,
        source_root=runtime.source_root,
        framework_commit=SIMPLE_FRAMEWORK_COMMIT,
    )


def _clean_child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("SIMPLE_SYNTH_") or name in {"MATLABPATH", "PYTHONHOME", "PYTHONPATH"}:
            environment.pop(name, None)
    return environment


def _matlab_environment(runtime: RuntimePaths, input_root: Path, output_root: Path) -> dict[str, str]:
    environment = _clean_child_environment()
    environment.update(
        {
            "SIMPLE_SYNTH_INPUT_ROOT": str(input_root),
            "SIMPLE_SYNTH_OUTPUT_ROOT": str(output_root),
            "SIMPLE_SYNTH_EEGLAB_ROOT": str(runtime.eeglab_root),
            "SIMPLE_SYNTH_GENERATOR_ROOT": str(runtime.source_root),
            "SIMPLE_SYNTH_PYTHON": str(runtime.python),
        }
    )
    return environment


def _stop_child(process: subprocess.Popen[bytes]) -> None:
    """Terminate the isolated child process group and wait for every exit path."""

    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            process.terminate()
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            process.kill()
        except ProcessLookupError:
            return
    process.wait(timeout=10)


def _run_child(command: list[str], *, cwd: Path, environment: dict[str, str]) -> int:
    """Run one noninteractive child and never leave it alive after interruption."""

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise ValidationError("MATLAB R2026a could not be started") from exc
    try:
        return process.wait()
    except BaseException:
        _stop_child(process)
        raise


def _default_native_preflight(runtime: RuntimePaths) -> None:
    """Start the exact native stack before the much costlier signal generation."""

    environment = _clean_child_environment()
    environment.update(
        {
            "SIMPLE_SYNTH_EEGLAB_ROOT": str(runtime.eeglab_root),
            "SIMPLE_SYNTH_GENERATOR_ROOT": str(runtime.source_root),
        }
    )
    command = "run('preflight_environment.m');"
    status = _run_child(
        [str(runtime.matlab), "-batch", command],
        cwd=runtime.source_root / "matlab",
        environment=environment,
    )
    if status != 0:
        raise ValidationError(
            f"MATLAB/EEGLAB prerequisite preflight failed (MATLAB exit {status}); generation did not start"
        )


def _default_packager(input_root: Path, output_root: Path, runtime: RuntimePaths) -> None:
    matlab_command = (
        "addpath(getenv('SIMPLE_SYNTH_EEGLAB_ROOT'));"
        "eeglab('nogui');"
        "cd(fullfile(getenv('SIMPLE_SYNTH_GENERATOR_ROOT'),'matlab'));"
        "run('package_and_verify_eeglab.m');"
    )
    status = _run_child(
        [str(runtime.matlab), "-batch", matlab_command],
        cwd=runtime.source_root / "matlab",
        environment=_matlab_environment(runtime, input_root, output_root),
    )
    if status != 0:
        raise ValidationError(
            f"Native EEGLAB packaging failed (MATLAB exit {status}); no dataset was promoted"
        )


def _expected_set_relative(subject: str, *, transfer: bool) -> str:
    prefix = "raw" if transfer else "data/raw"
    return f"{prefix}/sub-{subject}/ses-01/eeg/sub-{subject}_ses-01_run-01_eeg.set"


def _expected_dataset_rows() -> list[dict[str, str]]:
    return [
        {
            "subjectID": subject,
            "sessionID": "01",
            "runID": "01",
            "path_raw": f"data/raw/sub-{subject}/ses-01/eeg",
            "EEGfile_raw": f"sub-{subject}_ses-01_run-01_eeg.set",
        }
        for subject in EXPECTED_SUBJECTS
    ]


def _read_dataset_list(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValidationError("dataset_list.csv is absent, non-regular, or a symlink")
    payload = path.read_bytes()
    expected = canonical_csv_bytes(_expected_dataset_rows(), DATASET_LIST_HEADER)
    if payload != expected:
        raise ValidationError("dataset_list.csv bytes differ from the exact canonical 31-row contract")


def _inventory_tree(root: Path) -> tuple[set[str], set[str]]:
    directories: set[str] = set()
    files: set[str] = set()
    for current, names, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in names:
            path = current_path / name
            if path.is_symlink() or not path.is_dir():
                raise ValidationError("Dataset tree contains a symlink or non-directory object")
            directories.add(path.relative_to(root).as_posix())
        for name in filenames:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                raise ValidationError("Dataset tree contains a symlink or non-regular file")
            files.add(path.relative_to(root).as_posix())
    return directories, files


def _validate_raw_tree(raw_root: Path, *, transfer: bool) -> None:
    if raw_root.is_symlink() or not raw_root.is_dir():
        raise ValidationError("raw must be one ordinary directory")
    directories, files = _inventory_tree(raw_root)
    expected_directories = {
        relative
        for subject in EXPECTED_SUBJECTS
        for relative in (
            f"sub-{subject}",
            f"sub-{subject}/ses-01",
            f"sub-{subject}/ses-01/eeg",
        )
    }
    expected_files = {
        f"sub-{subject}/ses-01/eeg/sub-{subject}_ses-01_run-01_eeg.set"
        for subject in EXPECTED_SUBJECTS
    }
    if directories != expected_directories or files != expected_files:
        raise ValidationError("raw does not have the exact fixed 31-file subject/session/eeg hierarchy")
    if any(path.lower().endswith(".fdt") for path in files):
        raise ValidationError("raw contains a forbidden .fdt file")
    for relative in expected_files:
        if (raw_root / relative).stat(follow_symlinks=False).st_size <= 0:
            raise ValidationError("raw contains an empty .set file")


def validate_packaged_stage(root: Path) -> None:
    """Validate the selected transfer inputs from the internal rich bundle."""

    if root.is_symlink() or not root.is_dir():
        raise ValidationError("Native packaging did not create its expected ordinary directory")
    try:
        verify_manifest(root)
    except GeneratorError as exc:
        raise ValidationError("Native package MANIFEST.sha256 or source bytes differ") from exc
    _read_dataset_list(root / "data_lists" / "dataset_list.csv")
    _validate_raw_tree(root / "data" / "raw", transfer=False)


def validate_transfer_bundle(root: Path) -> None:
    """Require exactly the two human-facing entries and their fixed bijection."""

    if root.is_symlink() or not root.is_dir():
        raise ValidationError("Transfer partial is not one ordinary directory")
    entries = {entry.name for entry in root.iterdir()}
    if entries != {"dataset_list.csv", "raw"}:
        raise ValidationError("Final dataset must contain exactly dataset_list.csv and raw")
    _read_dataset_list(root / "dataset_list.csv")
    _validate_raw_tree(root / "raw", transfer=True)
    _, files = _inventory_tree(root)
    expected_files = {"dataset_list.csv"} | {
        _expected_set_relative(subject, transfer=True) for subject in EXPECTED_SUBJECTS
    }
    if files != expected_files or len(files) != 32:
        raise ValidationError("Dataset-list/.set inventory is not an exact 31-recording bijection")
    if any(path.lower().endswith(".fdt") for path in files):
        raise ValidationError("Final dataset contains a forbidden .fdt sidecar")
    all_paths = [root, *root.rglob("*")]
    for path in all_paths:
        expected_mode = 0o755 if path.is_dir() else 0o644
        if path.stat(follow_symlinks=False).st_mode & 0o777 != expected_mode:
            raise ValidationError("Final dataset modes must be owner-writable 0755/0644")


def _copy_transfer(packaged: Path, transfer: Path) -> None:
    if transfer.is_symlink() or not transfer.is_dir() or any(transfer.iterdir()):
        raise TransactionError("Owned transfer partial must begin as one empty ordinary directory")
    source_list = packaged / "data_lists" / "dataset_list.csv"
    destination_list = transfer / "dataset_list.csv"
    write_new_bytes(destination_list, source_list.read_bytes())
    for subject in EXPECTED_SUBJECTS:
        relative = Path(
            f"sub-{subject}/ses-01/eeg/sub-{subject}_ses-01_run-01_eeg.set"
        )
        source = packaged / "data" / "raw" / relative
        destination = transfer / "raw" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_digest = sha256_file(source)
        write_new_bytes(destination, source.read_bytes())
        if sha256_file(destination) != source_digest:
            raise ValidationError("A .set file changed while creating the transfer bundle")
    for directory, _, filenames in os.walk(transfer, topdown=False):
        directory_path = Path(directory)
        for filename in filenames:
            os.chmod(directory_path / filename, 0o644)
        os.chmod(directory_path, 0o755)
    validate_transfer_bundle(transfer)
    for directory, _, _ in os.walk(transfer, topdown=False):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_path(path: Path) -> None:
    if not _lexists(path):
        return
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)


def _clean_invocation(owned: Sequence[Path]) -> None:
    failures: list[str] = []
    for artifact in reversed(owned):
        try:
            _remove_path(artifact)
        except OSError:
            failures.append(artifact.name)
    if failures:
        raise TransactionError(f"Could not remove failed-build artifacts: {failures!r}")


def _default_reauditor(runtime: RuntimePaths) -> None:
    audit = audit_checkout(runtime.source_root)
    require_audited_module_origins(runtime.source_root)
    validate_lock_file(runtime.lock_file)
    validate_producing_interpreter(runtime.source_root)
    if str(audit["head"]) != runtime.generator_head:
        raise TransactionError("Generator HEAD changed after native packaging")


def orchestrate_build(
    *,
    paths: BuildPaths,
    runtime: RuntimePaths,
    settings: FrozenSettings,
    stage_builder: StageBuilder = _default_stage_builder,
    packager: Packager = _default_packager,
    promoter: Promoter = exclusive_atomic_rename,
    reauditor: Reauditor = _default_reauditor,
) -> Path:
    """Run both rich internal transactions and publish only the two-entry transfer."""

    owned: list[Path] = []
    try:
        for workspace in (paths.array_workspace, paths.packaging_workspace):
            os.mkdir(workspace, 0o755)
            owned.append(workspace)
            os.chmod(workspace, 0o755)
        print("1/3 Generating and independently reproducing the fixed synthetic signals...")
        stage_builder(paths.array_stage, runtime, settings)
        print("2/3 Packaging and round-trip checking 31 native one-file EEGLAB datasets...")
        packager(paths.array_stage, paths.packaged_stage, runtime)
        validate_packaged_stage(paths.packaged_stage)
        print("3/3 Preparing the minimal framework transfer folder...")
        os.mkdir(paths.transfer_partial, 0o755)
        owned.append(paths.transfer_partial)
        os.chmod(paths.transfer_partial, 0o755)
        _copy_transfer(paths.packaged_stage, paths.transfer_partial)
        validate_packaged_stage(paths.packaged_stage)
        validate_transfer_bundle(paths.transfer_partial)
        reauditor(runtime)

        _remove_path(paths.array_workspace)
        owned.remove(paths.array_workspace)
        _remove_path(paths.packaging_workspace)
        owned.remove(paths.packaging_workspace)
        if _lexists(paths.array_workspace) or _lexists(paths.packaging_workspace):
            raise TransactionError("Transient build inventory was not clean before final promotion")
        if paths.transfer_partial.is_symlink() or not paths.transfer_partial.is_dir():
            raise TransactionError("Exact transfer partial disappeared before final promotion")
        if _lexists(paths.final):
            raise TransactionError("Final output appeared during generation; refusing overwrite")
        print(f"Publishing the validated dataset as {FINAL_NAME}...")
        _fsync_directory(paths.parent)
        validate_transfer_bundle(paths.transfer_partial)
        promoter(paths.transfer_partial, paths.final)
        return paths.final
    except BaseException as original:
        try:
            _clean_invocation(owned)
        except GeneratorError as cleanup_error:
            raise cleanup_error from original
        raise


def build_dataset(
    parent: Path,
    source_root: Path,
    *,
    native_preflight: NativePreflight = _default_native_preflight,
) -> Path:
    parent = validate_parent(parent)
    runtime = discover_runtime(source_root)
    settings = load_settings(runtime.settings)
    print("Checking the exact MATLAB and EEGLAB prerequisites before generation...")
    native_preflight(runtime)
    paths = _unique_build_paths(parent)
    return orchestrate_build(paths=paths, runtime=runtime, settings=settings)


def run(arguments: Sequence[str] | None, *, source_root: Path) -> int:
    args = parser().parse_args(arguments)
    build_dataset(args.parent_directory, source_root)
    return 0


def main(*, source_root: Path) -> None:
    def interrupt_on_termination(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt_on_termination)
    try:
        raise SystemExit(run(sys.argv[1:], source_root=source_root))
    except GeneratorError as exc:
        raise SystemExit(f"generation refused: {exc}") from exc
    except KeyboardInterrupt as exc:
        raise SystemExit("generation interrupted; no partial dataset was promoted") from exc
