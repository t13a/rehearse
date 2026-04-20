"""Verify the Codex image entrypoint shell contract."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from script_helpers import REPO_ROOT, write_executable


def test_codex_entrypoint_runs_exec_with_prompt_argument(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "codex.argv"
    write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGV_DUMP\"\n"
    )

    work = tmp_path / "work"
    work.mkdir()
    home = tmp_path / "home" / ".codex"
    home.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CODEX_ARGV_DUMP": str(argv_dump),
            "CODEX_HOME": str(home),
            "HOME": str(tmp_path / "home"),
            "REHEARSE_AGENT_WORK_DIR": str(work),
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
    write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf 'OPENROUTER_API_KEY=%s\\n' \"$OPENROUTER_API_KEY\" > \"$CODEX_ENV_DUMP\"\n"
        "cat >/dev/null\n",
    )

    work = tmp_path / "work"
    work.mkdir()
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
            "REHEARSE_AGENT_WORK_DIR": str(work),
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
    work = tmp_path / "work"
    work.mkdir()
    home_root = tmp_path / "home"
    init_dir = home_root / ".rehearse" / "agent"
    init_dir.mkdir(parents=True)
    (init_dir / "init.sh").write_text("exit 42\n")

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_root),
            "REHEARSE_AGENT_WORK_DIR": str(work),
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
    write_executable(
        bin_dir / "codex",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGV_DUMP\"\n"
    )

    work = tmp_path / "work"
    work.mkdir()
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
            "REHEARSE_AGENT_WORK_DIR": str(work),
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
