"""Verify agent runner and container entrypoint shell contracts."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> Path:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_codex_runner_assembles_docker_env(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "docker.argv"
    _write_executable(
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
            "REHEARSE_SESSION_A": str(tmp_path / "A"),
            "REHEARSE_SESSION_B": str(tmp_path / "B"),
            "REHEARSE_AGENT_IMAGE": "rehearse-agent-codex:latest",
            "REHEARSE_AGENT_UID": "10000",
            "REHEARSE_AGENT_GID": "10000",
            "REHEARSE_AGENT_TIMEOUT": "3600",
            "REHEARSE_AGENT_MESSAGE": "go",
            "REHEARSE_AGENT_EXTRA_ARGS": "--oss",
            "OPENAI_API_KEY": "sk-test",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "run-agent-codex.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv[:2] == ["run", "--rm"]
    assert "-e" in argv
    assert "HOME=/home/agent" in argv
    assert "CODEX_HOME=/home/agent/.codex" in argv
    assert "OPENAI_API_KEY=sk-test" in argv
    assert "REHEARSE_AGENT_MESSAGE=go" in argv
    assert "REHEARSE_AGENT_EXTRA_ARGS=--oss" in argv
    assert argv[-1] == "rehearse-agent-codex:latest"


def test_codex_entrypoint_runs_exec_with_stdin_prompt(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "codex.argv"
    stdin_dump = tmp_path / "codex.stdin"
    _write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGV_DUMP\"\n"
        "cat > \"$CODEX_STDIN_DUMP\"\n",
    )

    data = tmp_path / "data"
    data.mkdir()
    home = tmp_path / "home" / ".codex"
    home.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CODEX_ARGV_DUMP": str(argv_dump),
            "CODEX_STDIN_DUMP": str(stdin_dump),
            "CODEX_HOME": str(home),
            "HOME": str(tmp_path / "home"),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
            "REHEARSE_AGENT_MESSAGE": "sort files",
            "REHEARSE_AGENT_EXTRA_ARGS": "--oss",
            "REHEARSE_AGENT_PROMPT_PATH": str(REPO_ROOT / "prompts" / "agent.md"),
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "codex" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv == [
        "--ask-for-approval",
        "never",
        "exec",
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        "--oss",
        "--color",
        "never",
        "-",
    ]
    assert "sort files" in stdin_dump.read_text()


def test_codex_entrypoint_resumes_existing_session(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "codex.argv"
    _write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGV_DUMP\"\n"
        "cat >/dev/null\n",
    )

    data = tmp_path / "data"
    data.mkdir()
    home = tmp_path / "home" / ".codex"
    (home / "sessions").mkdir(parents=True)
    (home / "sessions" / "session.jsonl").write_text("{}\n")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CODEX_ARGV_DUMP": str(argv_dump),
            "CODEX_HOME": str(home),
            "HOME": str(tmp_path / "home"),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
            "REHEARSE_AGENT_PROMPT_PATH": str(REPO_ROOT / "prompts" / "agent.md"),
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "codex" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv[:6] == [
        "--ask-for-approval",
        "never",
        "exec",
        "resume",
        "--last",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
