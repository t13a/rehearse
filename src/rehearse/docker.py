"""Docker wrappers for the three harness roles.

- `chown_container` hands ownership of `data/c/` to the agent UID at create time.
- `run_agent` launches the agent (or busybox placeholder) against a workspace.
- `cleanup_container` removes the workspace as root, since agent-owned files
  cannot be unlinked by the harness UID.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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


def chown_container(c_path: Path) -> None:
    """Recursively chown `c_path` to the agent UID/GID using a root container.

    `-h` so that symlinks themselves get re-owned (not their targets, which are
    read-only anyway).
    """
    cmd = [
        "docker", "run", "--rm",
        "--user", "0:0",
        "-v", f"{c_path}:{c_path}:rw",
        config.REHEARSE_HELPER_IMAGE,
        "chown", "-Rh",
        f"{config.REHEARSE_AGENT_UID}:{config.REHEARSE_AGENT_GID}",
        str(c_path),
    ]
    _run(cmd)


def run_agent(workspace: Path, a: Path, b: Path) -> int:
    """Run the agent container against the given workspace.

    Step 2 placeholder: busybox that lists c/ and d/ then touches d/.done.
    Returns the container exit code (does NOT raise on non-zero).
    """
    data = workspace / "data"
    cmd = [
        "docker", "run", "--rm",
        "--user", f"{config.REHEARSE_AGENT_UID}:{config.REHEARSE_AGENT_GID}",
        "-v", f"{data}:{data}:rw",
        "-v", f"{a}:{a}:ro",
        "-v", f"{b}:{b}:ro",
        "-w", str(data),
        config.REHEARSE_AGENT_IMAGE,
        "sh", "-c", "ls c/ && ls d/ && touch d/.done",
    ]
    return subprocess.run(cmd).returncode


def cleanup_container(workspace: Path) -> None:
    """Delete the workspace tree via a root container.

    Agent-owned entries under `c/` (and anything the agent moved into `d/`)
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
