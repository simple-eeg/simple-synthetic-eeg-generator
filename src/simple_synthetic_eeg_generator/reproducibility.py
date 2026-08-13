"""Three-fresh-process byte-reproducibility gate and final promotion."""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
import re
from pathlib import Path

from .canonical import relative_files, write_new_json
from .audit import audit_checkout, require_audited_module_origins, require_tracked_input
from .environment import validate_lock_file, validate_producing_interpreter
from .errors import TransactionError, ValidationError
from .settings import FrozenSettings, SIMPLE_FRAMEWORK_COMMIT
from .transaction import exclusive_atomic_rename, refuse_stale_partials, require_canonical_absent_output

MAX_WORKER_DIAGNOSTIC_CHARS = 600


def _compare_exact(left: Path, right: Path) -> None:
    left_files = [path.relative_to(left).as_posix() for path in relative_files(left)]
    right_files = [path.relative_to(right).as_posix() for path in relative_files(right)]
    if left_files != right_files:
        raise ValidationError("Fresh-process builds have different file sets")
    for relative in left_files:
        if (left / relative).read_bytes() != (right / relative).read_bytes():
            raise ValidationError(f"Fresh-process builds differ byte-for-byte: {relative}")


def _sanitise_worker_diagnostic(payload: bytes, source_root: Path) -> str:
    """Return a bounded path-free diagnostic without sample values or raw bytes."""

    text = payload.decode("utf-8", errors="replace")
    replacements = {
        str(source_root): "<generator-root>",
        str(Path.home()): "<home>",
        os.environ.get("TMPDIR", ""): "<tmp>",
    }
    for private, token in replacements.items():
        if private:
            text = text.replace(private, token)
    text = re.sub(r"/(?:Users|Volumes)/[^\s:'\"]+", "<private-path>", text)
    text = " ".join(text.split())
    return text[:MAX_WORKER_DIAGNOSTIC_CHARS]


def _write_worker_failure(
    scratch: Path,
    *,
    index: int,
    order: str,
    status: str,
    diagnostic: str,
    exit_code: int | None,
) -> None:
    write_new_json(
        scratch / f"worker-{index}-failure.json",
        {
            "schema": "simple-synthetic-worker-failure-v1",
            "status": status,
            "run_index": index,
            "order": order,
            "exit_code": exit_code,
            "diagnostic": diagnostic,
        },
    )


def _annotate_reproducibility(stage: Path) -> None:
    """Add the final receipt and rebuild manifest only after all three match."""

    from .canonical import build_manifest, write_new_bytes

    provenance = stage / "provenance"
    write_new_json(
        provenance / "reproducibility_receipt.json",
        {
            "schema": "simple-synthetic-reproducibility-v1",
            "status": "passed",
            "fresh_process_count": 3,
            "canonical_process_count": 2,
            "shuffled_process_count": 1,
            "comparison": "byte-identical file set and file contents before final receipt",
        },
    )
    manifest = stage / "MANIFEST.sha256"
    manifest.unlink()
    write_new_bytes(manifest, build_manifest(stage))


def _sanitised_worker_environment(source_root: Path, environment_root: Path) -> dict[str, str]:
    """Return the complete, minimal environment admitted to fresh workers."""

    if not environment_root.is_absolute() or environment_root.exists():
        raise TransactionError("Worker environment root must be an absent absolute path")
    home = environment_root / "home"
    temporary = environment_root / "tmp"
    mplconfig = environment_root / "mplconfig"
    xdg_cache = environment_root / "xdg-cache"
    for directory in (environment_root, home, temporary, mplconfig, xdg_cache):
        directory.mkdir()
    environment = {
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MPLCONFIGDIR": str(mplconfig),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "SIMPLE_SYNTH_AUDITED_SOURCE_ROOT": str(source_root),
        "SYSTEM_VERSION_COMPAT": "0",
        "TMPDIR": str(temporary),
        "XDG_CACHE_HOME": str(xdg_cache),
    }
    return environment


def _finalise_reproducible_runs(
    *, output: Path, runs: list[Path], control: Path, token: str
) -> Path:
    """Clean every noncanonical partial before the final exclusive promotion."""

    shutil.rmtree(runs[1])
    shutil.rmtree(runs[2])
    shutil.rmtree(control)
    expected = output.with_name(f"{output.name}.partial.{token}.canonical-1")
    actual_partials = sorted(output.parent.glob(f"{output.name}.partial.{token}.*"))
    if actual_partials != [expected] or runs[0] != expected:
        raise TransactionError("Reproducibility partial inventory is not exact before promotion")
    if output.exists() or output.is_symlink():
        raise TransactionError("Final output appeared before promotion")
    exclusive_atomic_rename(runs[0], output)
    return output


def generate_reproducibly(
    *,
    output: Path,
    settings: FrozenSettings,
    lock_file: Path,
    source_root: Path,
    framework_commit: str,
) -> Path:
    """Require canonical/canonical/shuffled fresh processes before promotion."""

    require_canonical_absent_output(output)
    audit_checkout(source_root)
    require_audited_module_origins(source_root)
    require_tracked_input(source_root, settings.source_path, "config/")
    require_tracked_input(source_root, lock_file, "requirements/")
    validate_lock_file(lock_file)
    interpreter = validate_producing_interpreter(source_root)
    if framework_commit != SIMPLE_FRAMEWORK_COMMIT:
        raise TransactionError(
            f"Framework commit must equal frozen checkpoint {SIMPLE_FRAMEWORK_COMMIT}"
        )
    refuse_stale_partials(output)
    token = secrets.token_hex(12)
    control = output.with_name(f"{output.name}.partial.{token}.control")
    runs = [
        output.with_name(f"{output.name}.partial.{token}.{label}")
        for label in ("canonical-1", "canonical-2", "shuffled-1")
    ]
    if any(path.exists() or path.is_symlink() for path in [control, *runs]):
        raise TransactionError("Unique reproducibility partial unexpectedly exists")
    os.mkdir(control, 0o755)
    try:
        bootstrap = (
            "import pathlib,sys;"
            "audited_src=pathlib.Path(sys.argv.pop(1));"
            "assert audited_src.is_absolute() and audited_src == audited_src.resolve(strict=True);"
            "sys.path.insert(0,str(audited_src));"
            "from simple_synthetic_eeg_generator.worker import main;"
            "main()"
        )
        for index, (destination, order) in enumerate(
            zip(runs, ("canonical", "canonical", "shuffled"), strict=True), start=1
        ):
            environment_root = control / f"worker-env-{index}"
            worker_environment = _sanitised_worker_environment(source_root, environment_root)
            command = [
                str(source_root / str(interpreter["lexical_path"])),
                "-B",
                "-X",
                f"pycache_prefix={environment_root / 'pycache'}",
                "-I",
                "-c",
                bootstrap,
                str(source_root / "src"),
                "--settings",
                str(settings.source_path),
                "--lock-file",
                str(lock_file),
                "--source-root",
                str(source_root),
                "--framework-commit",
                framework_commit,
                "--output",
                str(destination),
                "--order",
                order,
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1800,
                    env=worker_environment,
                )
            except subprocess.TimeoutExpired as exc:
                shutil.rmtree(environment_root)
                diagnostic = _sanitise_worker_diagnostic(exc.stderr or b"worker timed out", source_root)
                _write_worker_failure(
                    control,
                    index=index,
                    order=order,
                    status="timed-out-not-promoted-no-retry",
                    diagnostic=diagnostic,
                    exit_code=None,
                )
                raise ValidationError(
                    f"Fresh-process {order} build timed out; no retry is permitted; "
                    f"see sanitized worker-{index}-failure.json"
                ) from exc
            shutil.rmtree(environment_root)
            if completed.returncode != 0:
                diagnostic = _sanitise_worker_diagnostic(completed.stderr, source_root)
                _write_worker_failure(
                    control,
                    index=index,
                    order=order,
                    status="failed-not-promoted-no-retry",
                    diagnostic=diagnostic,
                    exit_code=completed.returncode,
                )
                raise ValidationError(
                    f"Fresh-process {order} build failed; no retry is permitted "
                    f"(exit {completed.returncode}); see sanitized worker-{index}-failure.json"
                )
        _compare_exact(runs[0], runs[1])
        _compare_exact(runs[0], runs[2])
        _annotate_reproducibility(runs[0])
        return _finalise_reproducible_runs(
            output=output, runs=runs, control=control, token=token
        )
    except BaseException as exc:
        marker = control / "REPRODUCIBILITY_FAILED_NOT_PROMOTED.json"
        if control.is_dir() and not marker.exists():
            try:
                write_new_json(
                    marker,
                    {
                        "schema": "simple-synthetic-reproducibility-failure-v1",
                        "status": "failed-not-promoted-no-retry",
                        "error_type": type(exc).__name__,
                    },
                )
            except BaseException:
                pass
        raise
