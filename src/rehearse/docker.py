"""Docker wrappers for the three harness roles.

- `chown_container` hands ownership of host paths to the agent UID at create time.
- `run_agent` invokes an external runner script that knows how to launch the agent.
- `cleanup_container` removes the workspace as root, since agent-owned files
  cannot be unlinked by the harness UID.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

from rehearse import config


class DockerError(RuntimeError):
    """Raised when a docker invocation returns non-zero."""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise DockerError(
            f"docker command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def chown_container(paths: Path | Iterable[Path]) -> None:
    """Recursively chown one or more host paths to the agent UID/GID.

    `-h` so that symlinks themselves get re-owned (not their targets, which are
    read-only anyway). Each path is bind-mounted at its own host path so that
    chown can address it without remapping.
    """
    if isinstance(paths, Path):
        path_list = [paths]
    else:
        path_list = list(paths)
    if not path_list:
        return

    cmd: list[str] = ["docker", "run", "--rm", "--user", "0:0"]
    for p in path_list:
        cmd += ["-v", f"{p}:{p}:rw"]
    cmd += [
        config.REHEARSE_HELPER_IMAGE,
        "chown", "-Rh",
        f"{config.REHEARSE_AGENT_UID}:{config.REHEARSE_AGENT_GID}",
    ]
    cmd += [str(p) for p in path_list]
    _run(cmd)


def run_agent(workspace: Path, a: Path, b: Path, *,
              message: str | None = None) -> int:
    """Invoke the external agent runner script.

    The runner is a bash script (`scripts/run-agent-cc.sh` by default) that
    knows how to launch the underlying agent (Claude Code, OpenCode, ...).
    The harness only passes parameters via environment variables and observes
    the runner's exit code. Tests swap `REHEARSE_AGENT_RUNNER` to point at a
    fake runner so they don't need a real agent image or API key.

    Returns the runner's exit code (does NOT raise on non-zero).
    """
    env = os.environ.copy()
    env["REHEARSE_SESSION_WORKSPACE"] = str(workspace)
    env["REHEARSE_SESSION_DATA"] = str(workspace / "data")
    env["REHEARSE_SESSION_HOME"] = str(workspace / "home" / "agent")
    env["REHEARSE_SESSION_A"] = str(a)
    env["REHEARSE_SESSION_B"] = str(b)
    env["REHEARSE_AGENT_IMAGE"] = config.REHEARSE_AGENT_IMAGE
    env["REHEARSE_AGENT_UID"] = str(config.REHEARSE_AGENT_UID)
    env["REHEARSE_AGENT_GID"] = str(config.REHEARSE_AGENT_GID)
    env["REHEARSE_AGENT_TIMEOUT"] = str(config.REHEARSE_AGENT_TIMEOUT)
    if config.REHEARSE_MCP_CONFIG is not None:
        env["REHEARSE_MCP_CONFIG"] = str(config.REHEARSE_MCP_CONFIG)
    if message is not None:
        env["REHEARSE_AGENT_MESSAGE"] = message

    runner = str(config.REHEARSE_AGENT_RUNNER)
    return subprocess.run([runner], env=env).returncode


def cleanup_container(workspace: Path) -> None:
    """Delete the workspace tree via a root container.

    Agent-owned entries under `inbox/` (and anything the agent moved into `outbox/`)
    cannot be unlinked by the harness UID, so we run `rm -rf` as root in a
    container that has the workspace bind-mounted.

    We mount the PARENT of the workspace — mounting the workspace itself
    would make it a mount point, and `rm` cannot unlink its own mount point
    (EBUSY). Mounting the parent lets us delete children normally.
    """
    parent = workspace.parent
    cmd = [
        "docker", "run", "--rm",
        "--user", "0:0",
        "-v", f"{parent}:{parent}:rw",
        config.REHEARSE_HELPER_IMAGE,
        "rm", "-rf", str(workspace),
    ]
    _run(cmd)
