"""Home skeleton preparation and copying."""

from __future__ import annotations

import shutil
from pathlib import Path

from rehearse import config
from rehearse.profile import ProfileError, validate_name


def skeleton_path(name: str) -> Path:
    validate_name(name)
    if name in (".", ".."):
        raise ProfileError("invalid skeleton name: must not be '.' or '..'")
    return config.SKELETONS_DIR / name


def ensure_default_skeleton() -> None:
    path = skeleton_path("default")
    path.mkdir(parents=True, exist_ok=True)


def resolve_skeleton(name: str) -> Path:
    if name == "default":
        ensure_default_skeleton()
    path = skeleton_path(name)
    if not path.exists():
        raise ProfileError(f"skeleton not found: {name}")
    if not path.is_dir() or path.is_symlink():
        raise ProfileError(f"skeleton must be a real directory: {path}")
    return path


def copy_skeleton(name: str, dest: Path) -> None:
    src = resolve_skeleton(name)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, symlinks=True, dirs_exist_ok=True)
