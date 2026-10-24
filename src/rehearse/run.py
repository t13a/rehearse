"""Agent runner script contract for `rehearse run` and `rehearse debug`."""

from __future__ import annotations

import os
import subprocess
import sys
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
    log_path: Path | None = None,
) -> int:
    """Invoke the external agent runner script in normal agent mode.

    The message replaces the profile's agent_message; they are not combined.
    """
    if message is None:
        message = profile.agent_message
    env = _runner_env(
        session_dir, a, b, profile, run_lock_path=run_lock_path, message=message
    )
    env["REHEARSE_RUNNER_MODE"] = "run"

    runner = str(profile.agent_runner)
    if log_path is None:
        return subprocess.run([runner], env=env).returncode
    return _run_with_log([runner], env, log_path)


def _run_with_log(argv: list[str], env: dict[str, str], log_path: Path) -> int:
    """Run argv, copying its stdout and stderr to the terminal and to log_path."""
    log_path.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as log, subprocess.Popen(
        argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ) as proc:
        assert proc.stdout is not None
        out = sys.stdout.buffer
        while chunk := os.read(proc.stdout.fileno(), 65536):
            out.write(chunk)
            out.flush()
            log.write(chunk)
            log.flush()
    return proc.returncode


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
