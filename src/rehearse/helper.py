"""Root helper script contract for privileged workspace operations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

from rehearse import config
from rehearse.profile import EffectiveProfile


def _helper_env(mount: Path, profile: EffectiveProfile) -> dict[str, str]:
    env = os.environ.copy()
    env["REHEARSE_HELPER_IMAGE"] = profile.helper_image
    env["REHEARSE_HELPER_MOUNT"] = str(mount)
    return env


def chown_paths(
    mount: Path,
    paths: Path | Iterable[Path],
    profile: EffectiveProfile,
    *,
    uid: int,
    gid: int,
) -> None:
    """Recursively chown one or more host paths to a numeric UID/GID."""
    if isinstance(paths, Path):
        path_list = [paths]
    else:
        path_list = list(paths)
    if not path_list:
        return

    subprocess.run(
        [
            str(config.DEFAULT_DOCKER_HELPER),
            "chown",
            "-Rh",
            f"{uid}:{gid}",
            *[str(p) for p in path_list],
        ],
        env=_helper_env(mount, profile),
        check=True,
    )


def remove_tree(mount: Path, path: Path, profile: EffectiveProfile) -> None:
    """Delete a workspace tree via the root helper script."""
    subprocess.run(
        [
            str(config.DEFAULT_DOCKER_HELPER),
            "rm",
            "-rf",
            str(path),
        ],
        env=_helper_env(mount, profile),
        check=True,
    )
