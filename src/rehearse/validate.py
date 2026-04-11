"""Pre-flight validation for `rehearse create`."""

from __future__ import annotations

import os
from pathlib import Path


class PreflightError(Exception):
    """Raised when A or B fails pre-flight checks."""


def _check_directory(label: str, path: Path) -> None:
    if not path.exists():
        raise PreflightError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise PreflightError(f"{label} is not a directory: {path}")
    if path.is_symlink():
        raise PreflightError(f"{label} is itself a symlink: {path}")


def _check_no_symlinks(label: str, root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dp = Path(dirpath)
        for name in dirnames + filenames:
            entry = dp / name
            if entry.is_symlink():
                raise PreflightError(
                    f"{label} contains a symlink (unsupported): {entry}"
                )


def _check_same_filesystem(a: Path, b: Path) -> None:
    if a.stat().st_dev != b.stat().st_dev:
        raise PreflightError(
            f"A and B are on different filesystems: {a} (dev={a.stat().st_dev}) "
            f"vs {b} (dev={b.stat().st_dev})"
        )


def preflight(a: Path, b: Path) -> None:
    """Validate A and B before creating a session.

    Raises PreflightError on any failure.
    """
    _check_directory("A", a)
    _check_directory("B", b)
    _check_same_filesystem(a, b)
    _check_no_symlinks("A", a)
    _check_no_symlinks("B", b)
