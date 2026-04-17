"""Docker runner wrappers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

from rehearse import config
from rehearse.profile import EffectiveProfile


RUN_LOCK_BUSY_EXIT = 75


def _helper_env(mount: Path, profile: EffectiveProfile) -> dict[str, str]:
    env = os.environ.copy()
    env["REHEARSE_HELPER_IMAGE"] = profile.helper_image
    env["REHEARSE_HELPER_MOUNT"] = str(mount)
    return env


def chown_container(
    workspace: Path,
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
        env=_helper_env(workspace.parent, profile),
        check=True,
    )


def run_agent(
    workspace: Path,
    a: Path,
    b: Path,
    profile: EffectiveProfile,
    *,
    message: str | None = None,
) -> int:
    """Invoke the external agent runner script.

    The runner is a bash script (`scripts/docker-runner.sh` by default). The
    harness passes parameters via environment variables and observes the
    runner's exit code. Tests can set profile.agent_runner to a fake runner.

    Returns the runner's exit code (does NOT raise on non-zero).
    """
    env = os.environ.copy()
    env["REHEARSE_SESSION_WORKSPACE"] = str(workspace)
    env["REHEARSE_SESSION_DATA"] = str(workspace / "data")
    env["REHEARSE_SESSION_HOME"] = str(workspace / "home" / "agent")
    env["REHEARSE_SESSION_RUN_LOCK"] = str(workspace / "run.lock")
    env["REHEARSE_SESSION_A"] = str(a)
    env["REHEARSE_SESSION_B"] = str(b)
    env["REHEARSE_AGENT_IMAGE"] = profile.agent_image
    env["REHEARSE_AGENT_UID"] = str(profile.agent_uid)
    env["REHEARSE_AGENT_GID"] = str(profile.agent_gid)
    env["REHEARSE_AGENT_TIMEOUT"] = str(profile.agent_timeout)
    if profile.agent_extra_args is not None:
        env["REHEARSE_AGENT_EXTRA_ARGS"] = profile.agent_extra_args
    else:
        env.pop("REHEARSE_AGENT_EXTRA_ARGS", None)
    if message is not None:
        env["REHEARSE_AGENT_MESSAGE"] = message
    else:
        env.pop("REHEARSE_AGENT_MESSAGE", None)

    runner = str(profile.agent_runner)
    return subprocess.run([runner], env=env).returncode


def cleanup_container(workspace: Path, profile: EffectiveProfile) -> None:
    """Delete the workspace tree via a root helper container."""
    subprocess.run(
        [
            str(config.DEFAULT_DOCKER_HELPER),
            "rm",
            "-rf",
            str(workspace),
        ],
        env=_helper_env(workspace.parent, profile),
        check=True,
    )
