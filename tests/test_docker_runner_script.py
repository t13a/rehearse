"""Verify the docker-runner.sh shell contract."""

from __future__ import annotations

import fcntl
import os
import subprocess
from pathlib import Path

from script_helpers import REPO_ROOT, write_executable


def test_assembles_args_for_run(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "ws").mkdir()
    argv_dump = tmp_path / "docker.argv"
    write_executable(
        bin_dir / "docker",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$DOCKER_ARGV_DUMP\"\n",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "DOCKER_ARGV_DUMP": str(argv_dump),
            "REHEARSE_SESSION_WORKSPACE": str(tmp_path / "ws"),
            "REHEARSE_SESSION_DATA": str(tmp_path / "ws" / "data"),
            "REHEARSE_SESSION_HOME": str(tmp_path / "ws" / "home" / "agent"),
            "REHEARSE_SESSION_RUN_LOCK": str(tmp_path / "ws" / "run.lock"),
            "REHEARSE_SESSION_A": str(tmp_path / "A"),
            "REHEARSE_SESSION_B": str(tmp_path / "B"),
            "REHEARSE_AGENT_IMAGE": "rehearse-agent-codex:latest",
            "REHEARSE_AGENT_UID": "10000",
            "REHEARSE_AGENT_GID": "10000",
            "REHEARSE_AGENT_TIMEOUT": "3600",
            "REHEARSE_RUNNER_MODE": "run",
            "REHEARSE_AGENT_MESSAGE": "go",
            "REHEARSE_AGENT_EXTRA_ARGS": "--oss",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "docker-runner.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv[:2] == ["run", "--rm"]
    assert "-e" in argv
    assert "HOME=/home/agent" in argv
    assert "REHEARSE_AGENT_MESSAGE=go" in argv
    assert "REHEARSE_AGENT_EXTRA_ARGS=--oss" in argv
    assert argv[-1] == "rehearse-agent-codex:latest"


def test_assembles_args_for_debug(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "ws").mkdir()
    argv_dump = tmp_path / "docker.argv"
    write_executable(
        bin_dir / "docker",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$DOCKER_ARGV_DUMP\"\n",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "DOCKER_ARGV_DUMP": str(argv_dump),
            "REHEARSE_SESSION_WORKSPACE": str(tmp_path / "ws"),
            "REHEARSE_SESSION_DATA": str(tmp_path / "ws" / "data"),
            "REHEARSE_SESSION_HOME": str(tmp_path / "ws" / "home" / "agent"),
            "REHEARSE_SESSION_RUN_LOCK": str(tmp_path / "ws" / "run.lock"),
            "REHEARSE_SESSION_A": str(tmp_path / "A"),
            "REHEARSE_SESSION_B": str(tmp_path / "B"),
            "REHEARSE_AGENT_IMAGE": "rehearse-agent-codex:latest",
            "REHEARSE_AGENT_UID": "10000",
            "REHEARSE_AGENT_GID": "10000",
            "REHEARSE_AGENT_TIMEOUT": "3600",
            "REHEARSE_RUNNER_MODE": "debug",
            "REHEARSE_DEBUG_ENTRYPOINT": "/bin/bash",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "docker-runner.sh"), "-lc", "id"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv[:2] == ["run", "--rm"]
    assert "--entrypoint" in argv
    entrypoint_index = argv.index("--entrypoint")
    assert argv[entrypoint_index + 1] == "/bin/bash"
    image_index = argv.index("rehearse-agent-codex:latest")
    assert argv[image_index:] == ["rehearse-agent-codex:latest", "-lc", "id"]


def test_fails_when_session_lock_is_held(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "ws").mkdir()
    docker_called = tmp_path / "docker.called"
    write_executable(
        bin_dir / "docker",
        "#!/bin/bash\n"
        "touch \"$DOCKER_CALLED\"\n",
    )

    lock_path = tmp_path / "ws" / "run.lock"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "DOCKER_CALLED": str(docker_called),
            "REHEARSE_SESSION_WORKSPACE": str(tmp_path / "ws"),
            "REHEARSE_SESSION_DATA": str(tmp_path / "ws" / "data"),
            "REHEARSE_SESSION_HOME": str(tmp_path / "ws" / "home" / "agent"),
            "REHEARSE_SESSION_RUN_LOCK": str(lock_path),
            "REHEARSE_SESSION_A": str(tmp_path / "A"),
            "REHEARSE_SESSION_B": str(tmp_path / "B"),
            "REHEARSE_AGENT_IMAGE": "rehearse-agent:test",
            "REHEARSE_AGENT_UID": "10000",
            "REHEARSE_AGENT_GID": "10000",
            "REHEARSE_AGENT_TIMEOUT": "3600",
            "REHEARSE_RUNNER_MODE": "run",
        }
    )

    with lock_path.open("w") as fd:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / "docker-runner.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 75

    assert not docker_called.exists()
