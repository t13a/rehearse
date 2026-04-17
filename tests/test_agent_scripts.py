"""Verify agent runner and container entrypoint shell contracts."""

from __future__ import annotations

import fcntl
import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> Path:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_docker_runner_assembles_docker_env(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "ws").mkdir()
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


def test_docker_runner_assembles_debug_entrypoint(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "ws").mkdir()
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


def test_docker_helper_assembles_root_helper_container(
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
            "REHEARSE_HELPER_IMAGE": "busybox:test",
            "REHEARSE_HELPER_MOUNT": str(tmp_path / "sessions"),
        }
    )

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "docker-helper.sh"),
            "chown",
            "-Rh",
            "10000:10000",
            str(tmp_path / "sessions" / "123" / "home" / "agent"),
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv == [
        "run",
        "--rm",
        "--user",
        "0:0",
        "-v",
        f"{tmp_path / 'sessions'}:{tmp_path / 'sessions'}:rw",
        "busybox:test",
        "chown",
        "-Rh",
        "10000:10000",
        str(tmp_path / "sessions" / "123" / "home" / "agent"),
    ]


def test_agent_runners_fail_when_session_lock_is_held(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "ws").mkdir()
    docker_called = tmp_path / "docker.called"
    _write_executable(
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


def test_codex_entrypoint_runs_exec_with_prompt_argument(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "codex.argv"
    _write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGV_DUMP\"\n"
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
            "CODEX_HOME": str(home),
            "HOME": str(tmp_path / "home"),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
            "REHEARSE_AGENT_MESSAGE": "sort files",
            "REHEARSE_AGENT_EXTRA_ARGS": "--oss",
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
        "--sandbox",
        "danger-full-access",
        "--oss",
        "exec",
        "--skip-git-repo-check",
        "sort files",
    ]


def test_codex_entrypoint_sources_agent_init(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env_dump = tmp_path / "codex.env"
    _write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf 'OPENROUTER_API_KEY=%s\\n' \"$OPENROUTER_API_KEY\" > \"$CODEX_ENV_DUMP\"\n"
        "cat >/dev/null\n",
    )

    data = tmp_path / "data"
    data.mkdir()
    home_root = tmp_path / "home"
    home = home_root / ".codex"
    init_dir = home_root / ".rehearse" / "agent"
    home.mkdir(parents=True)
    init_dir.mkdir(parents=True)
    (init_dir / "init.sh").write_text("export OPENROUTER_API_KEY=sk-openrouter\n")

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CODEX_ENV_DUMP": str(env_dump),
            "CODEX_HOME": str(home),
            "HOME": str(home_root),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "codex" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert env_dump.read_text() == "OPENROUTER_API_KEY=sk-openrouter\n"


def test_codex_entrypoint_fails_when_agent_init_fails(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    home_root = tmp_path / "home"
    init_dir = home_root / ".rehearse" / "agent"
    init_dir.mkdir(parents=True)
    (init_dir / "init.sh").write_text("exit 42\n")

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_root),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "codex" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 42


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
            "REHEARSE_AGENT_EXTRA_ARGS": "--oss",
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
        "--sandbox",
        "danger-full-access",
        "--oss",
        "exec",
    ]
    assert argv[6:] == [
        "resume",
        "--last",
        "--skip-git-repo-check",
        "作業を再開してください。",
    ]


def test_claude_entrypoint_runs_with_custom_message(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "claude.argv"
    _write_executable(
        bin_dir / "claude",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CLAUDE_ARGV_DUMP\"\n",
    )

    data = tmp_path / "data"
    data.mkdir()
    home_root = tmp_path / "home"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CLAUDE_ARGV_DUMP": str(argv_dump),
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "HOME": str(home_root),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
            "REHEARSE_AGENT_MESSAGE": "sort files",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "claude" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert "--append-system-prompt" not in argv
    assert argv == [
        "--print",
        "--permission-mode",
        "bypassPermissions",
        "sort files",
    ]


def test_claude_entrypoint_continues_with_resume_message(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "claude.argv"
    _write_executable(
        bin_dir / "claude",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CLAUDE_ARGV_DUMP\"\n",
    )

    data = tmp_path / "data"
    data.mkdir()
    home_root = tmp_path / "home"
    project_dir = home_root / ".claude" / "projects" / "session"
    project_dir.mkdir(parents=True)
    (project_dir / "history.jsonl").write_text("{}\n")
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CLAUDE_ARGV_DUMP": str(argv_dump),
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "HOME": str(home_root),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "claude" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv == [
        "--print",
        "--permission-mode",
        "bypassPermissions",
        "--continue",
        "作業を再開してください。",
    ]


def test_claude_entrypoint_sources_agent_init_before_key_check(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env_dump = tmp_path / "claude.env"
    _write_executable(
        bin_dir / "claude",
        "#!/bin/bash\n"
        "printf 'ANTHROPIC_API_KEY=%s\\n' \"$ANTHROPIC_API_KEY\" > \"$CLAUDE_ENV_DUMP\"\n",
    )

    data = tmp_path / "data"
    data.mkdir()
    home_root = tmp_path / "home"
    init_dir = home_root / ".rehearse" / "agent"
    init_dir.mkdir(parents=True)
    (init_dir / "init.sh").write_text("export ANTHROPIC_API_KEY=sk-ant-test\n")

    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CLAUDE_ENV_DUMP": str(env_dump),
            "HOME": str(home_root),
            "REHEARSE_WORKSPACE_DATA": str(data),
            "REHEARSE_AGENT_TIMEOUT": "5",
        }
    )

    result = subprocess.run(
        [str(REPO_ROOT / "docker" / "claude" / "entrypoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert env_dump.read_text() == "ANTHROPIC_API_KEY=sk-ant-test\n"
