"""One-choice, fail-closed build of the disposable SIMPLE transfer dataset."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import signal
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .audit import audit_checkout, require_audited_module_origins
from .canonical import (
    canonical_csv_bytes,
    sha256_file,
    verify_manifest,
    write_new_bytes,
)
from .environment import runtime_environment_receipt
from .platform_support import sync_directory, venv_python
from .errors import GeneratorError, TransactionError, ValidationError
from .settings import EXPECTED_SUBJECTS, FrozenSettings, load_settings
from .transaction import build_array_stage, exclusive_atomic_rename

FINAL_NAME = "simple-synthetic-eeg-demo"
DEFAULT_APPLICATIONS_ROOT = (
    Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "MATLAB"
    if os.name == "nt" else Path("/usr/local/MATLAB" if sys.platform.startswith("linux") else "/Applications")
)
MATLAB_FILENAME = "matlab.exe" if os.name == "nt" else "matlab"
MATLAB_OVERRIDE_VARIABLE = "SIMPLE_SYNTH_MATLAB_EXECUTABLE"
EEGLAB_OVERRIDE_VARIABLE = "SIMPLE_SYNTH_EEGLAB_ROOT"
MATLAB_APPLICATION_PATTERN = re.compile(r"(?:MATLAB_)?R([0-9]{4})([ab])(?:\.app)?\Z")
EEGLAB_DIRECTORY_PATTERN = re.compile(r"eeglab([0-9]+(?:\.[0-9]+)*)\Z")
DATASET_LIST_HEADER = ("subjectID", "sessionID", "runID", "path_raw", "EEGfile_raw")


@dataclass(frozen=True)
class RuntimePaths:
    source_root: Path
    python: Path
    matlab: Path
    eeglab_root: Path
    settings: Path
    generator_head: str
    python_runtime: dict[str, object]


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
        prog="python generate_dataset",
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


def _require_canonical_executable(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise TransactionError(f"{label} must be an absolute path")
    try:
        canonical = path.resolve(strict=True)
    except OSError as exc:
        raise TransactionError(f"{label} cannot be resolved") from exc
    if canonical != path or path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        raise TransactionError(f"{label} must be one canonical executable file without symlinks")
    return path


def _select_matlab(
    *, applications_root: Path, environment: Mapping[str, str]
) -> Path:
    override = environment.get(MATLAB_OVERRIDE_VARIABLE, "")
    if override:
        return _require_canonical_executable(Path(override), "Selected MATLAB executable")

    candidates: list[tuple[tuple[int, int], Path]] = []
    for application in applications_root.glob("*"):
        match = MATLAB_APPLICATION_PATTERN.fullmatch(application.name)
        if match is None:
            continue
        try:
            _require_canonical_directory(application, "MATLAB application")
            executable = _require_canonical_executable(
                application / "bin" / MATLAB_FILENAME, "MATLAB executable"
            )
        except TransactionError:
            continue
        half = 0 if match.group(2) == "a" else 1
        candidates.append(((int(match.group(1)), half), executable))
    if not candidates:
        on_path = shutil.which(MATLAB_FILENAME, path=environment.get("PATH"))
        if on_path:
            return _require_canonical_executable(Path(on_path).resolve(strict=True), "MATLAB executable")
        raise TransactionError(
            "No usable MATLAB installation was found in its standard location or PATH; "
            f"set {MATLAB_OVERRIDE_VARIABLE} to its executable"
        )
    candidates.sort(key=lambda item: (item[0], item[1].as_posix()), reverse=True)
    highest = candidates[0][0]
    if sum(rank == highest for rank, _ in candidates) != 1:
        raise TransactionError("More than one MATLAB installation has the highest detected release")
    return candidates[0][1]


def _select_eeglab(*, home: Path, environment: Mapping[str, str]) -> Path:
    override = environment.get(EEGLAB_OVERRIDE_VARIABLE, "")
    if override:
        selected = _require_canonical_directory(Path(override), "Selected EEGLAB installation")
        if not (selected / "eeglab.m").is_file() or (selected / "eeglab.m").is_symlink():
            raise TransactionError("Selected EEGLAB installation does not contain a regular eeglab.m")
        return selected

    matlab_home = home / "Documents" / "MATLAB"
    matlab_home = _require_canonical_directory(matlab_home, "User MATLAB directory")
    candidates: list[tuple[tuple[int, ...], Path]] = []
    for candidate in matlab_home.glob("eeglab*"):
        match = EEGLAB_DIRECTORY_PATTERN.fullmatch(candidate.name)
        if match is None:
            continue
        try:
            selected = _require_canonical_directory(candidate, "EEGLAB installation")
        except TransactionError:
            continue
        entrypoint = selected / "eeglab.m"
        if not entrypoint.is_file() or entrypoint.is_symlink():
            continue
        rank = tuple(int(part) for part in match.group(1).split("."))
        candidates.append((rank, selected))
    if not candidates:
        raise TransactionError(
            "No usable eeglab<version> installation was found in Documents/MATLAB; "
            f"set {EEGLAB_OVERRIDE_VARIABLE} to a canonical EEGLAB directory if installed elsewhere"
        )
    candidates.sort(key=lambda item: (item[0], item[1].as_posix()), reverse=True)
    highest = candidates[0][0]
    if sum(rank == highest for rank, _ in candidates) != 1:
        raise TransactionError("More than one EEGLAB installation has the highest detected version")
    return candidates[0][1]


def _has_git_boundary(path: Path) -> bool:
    """Reject worktrees, Git directories, bare repositories, and `.git` ancestors."""

    for ancestor in (path, *path.parents):
        if _lexists(ancestor / ".git"):
            return True
    try:
        completed = subprocess.run(
            [
                "git",
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


def discover_runtime(
    source_root: Path,
    *,
    home: Path | None = None,
    applications_root: Path = DEFAULT_APPLICATIONS_ROOT,
    environment: Mapping[str, str] | None = None,
) -> RuntimePaths:
    """Select installed runtimes by location; native capabilities are tested separately."""

    source_root = _require_canonical_directory(source_root, "Generator checkout")
    python = venv_python(source_root)
    selected_environment = os.environ if environment is None else environment
    matlab = _select_matlab(
        applications_root=applications_root, environment=selected_environment
    )
    eeglab_root = _select_eeglab(
        home=Path.home() if home is None else home,
        environment=selected_environment,
    )
    settings = source_root / "config" / "generator_settings.json"
    audit = audit_checkout(source_root)
    require_audited_module_origins(source_root)
    python_runtime = runtime_environment_receipt(source_root)
    return RuntimePaths(
        source_root=source_root,
        python=python,
        matlab=matlab,
        eeglab_root=eeglab_root,
        settings=settings,
        generator_head=str(audit["head"]),
        python_runtime=python_runtime,
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
    build_array_stage(
        output=output,
        settings=settings,
        source_root=runtime.source_root,
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
    if os.name == "nt":
        # taskkill terminates MATLAB and any descendants, not just its launcher.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False,
        )
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
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
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise ValidationError("The selected MATLAB executable could not be started") from exc
    try:
        return process.wait()
    except BaseException:
        _stop_child(process)
        raise


def _matlab_batch_command(runtime: RuntimePaths, statement: str) -> list[str]:
    # The Windows launcher needs -wait to return MATLAB's exit status.
    wait = ["-wait"] if os.name == "nt" else []
    return [str(runtime.matlab), *wait, "-batch", statement]


def _default_native_preflight(runtime: RuntimePaths) -> None:
    """Check the selected native stack before the costlier signal generation."""

    environment = _clean_child_environment()
    environment.update(
        {
            "SIMPLE_SYNTH_EEGLAB_ROOT": str(runtime.eeglab_root),
            "SIMPLE_SYNTH_GENERATOR_ROOT": str(runtime.source_root),
        }
    )
    command = "run('preflight_environment.m');"
    status = _run_child(
        _matlab_batch_command(runtime, command),
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
        _matlab_batch_command(runtime, matlab_command),
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
        if os.name == "nt":
            if not os.access(path, os.W_OK):
                raise ValidationError("Final dataset must be writable")
        else:
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
        sync_directory(Path(directory))


def _fsync_directory(path: Path) -> None:
    sync_directory(path)


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
    if runtime_environment_receipt(runtime.source_root) != runtime.python_runtime:
        raise TransactionError("Python runtime changed after native packaging")
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
        print("1/3 Generating and scientifically validating the fixed synthetic signals...")
        stage_builder(paths.array_stage, runtime, settings)
        print("2/3 Packaging and round-trip checking 31 native one-file EEGLAB datasets...")
        packager(paths.array_stage, paths.packaged_stage, runtime)
        validate_packaged_stage(paths.packaged_stage)
        print("3/3 Preparing the minimal SIMPLE transfer folder...")
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
    packages = dict(runtime.python_runtime["packages"])
    package_text = ", ".join(f"{name} {packages[name]}" for name in sorted(packages))
    print(
        f"Using Python {runtime.python_runtime['python_version']} "
        f"({runtime.python_runtime['machine']}); {package_text}"
    )
    print(f"Using MATLAB executable: {runtime.matlab}")
    print(f"Using EEGLAB installation: {runtime.eeglab_root}")
    print("Checking MATLAB and EEGLAB capabilities before generation...")
    native_preflight(runtime)
    paths = _unique_build_paths(parent)
    return orchestrate_build(paths=paths, runtime=runtime, settings=settings)


def run(arguments: Sequence[str] | None, *, source_root: Path) -> int:
    args = parser().parse_args(arguments)
    build_dataset(Path(os.path.abspath(args.parent_directory)), source_root)
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
