"""Agent runner script contract for `rehearse run` and `rehearse debug`."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rehearse.profile import EffectiveProfile


RUN_LOCK_BUSY_EXIT = 75


def run_agent(
    session_dir: Path,
    a: Path,
    b: Path,
    profile: EffectiveProfile,
    *,
    run_lock_path: Path,
    message: str | None = None,
) -> int:
    """Invoke the external agent runner script in normal agent mode."""
    env = _runner_env(
        session_dir, a, b, profile, run_lock_path=run_lock_path, message=message
    )
    env["REHEARSE_RUNNER_MODE"] = "run"

    runner = str(profile.agent_runner)
    return subprocess.run([runner], env=env).returncode


def run_debug(
    session_dir: Path,
    a: Path,
    b: Path,
    profile: EffectiveProfile,
    *,
    run_lock_path: Path,
    argv: list[str],
) -> int:
    """Invoke the external agent runner script with an entrypoint override."""
    env = _runner_env(
        session_dir, a, b, profile, run_lock_path=run_lock_path, message=None
    )
    env["REHEARSE_RUNNER_MODE"] = "debug"
    env["REHEARSE_DEBUG_ENTRYPOINT"] = argv[0]

    runner = str(profile.agent_runner)
    return subprocess.run([runner, *argv[1:]], env=env).returncode


def _runner_env(
    session_dir: Path,
    a: Path,
    b: Path,
    profile: EffectiveProfile,
    *,
    run_lock_path: Path,
    message: str | None,
) -> dict[str, str]:
    """Build the env-var contract shared by run and debug."""
    env = os.environ.copy()
    env["REHEARSE_SESSION_DIR"] = str(session_dir)
    env["REHEARSE_AGENT_WORK_DIR"] = str(session_dir / "work")
    env["REHEARSE_AGENT_HOME"] = str(session_dir / "home" / "agent")
    env["REHEARSE_SESSION_RUN_LOCK"] = str(run_lock_path)
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
    env.pop("REHEARSE_DEBUG_ENTRYPOINT", None)
    return env
