"""Small operating-system adapters shared by the generator and its packager."""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path


def venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sync_directory(path: Path) -> None:
    """Sync directory entries where supported; file contents are synced separately."""
    if os.name == "nt":
        return  # Windows does not expose directory fsync through Python.
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def rename_directory_exclusive(source: Path, destination: Path) -> None:
    """Atomically rename on one filesystem, never replacing an existing entry.

    Do not replace this with an existence check followed by os.rename: Unix
    rename can overwrite an empty directory created between those operations.
    Unsupported filesystems fail without a copying or overwriting fallback.
    """
    if os.name == "nt":
        os.rename(source, destination)  # Windows refuses every existing target.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        arguments = (os.fsencode(source), os.fsencode(destination), 0x00000004)
    elif sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError as exc:
            raise OSError(errno.ENOSYS, "This Linux runtime lacks no-replace rename") from exc
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        arguments = (-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise OSError(errno.ENOSYS, "No safe directory rename is available on this operating system")
    rename.restype = ctypes.c_int
    ctypes.set_errno(0)
    if rename(*arguments) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))
