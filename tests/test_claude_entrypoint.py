"""Verify the Claude image entrypoint shell contract."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from script_helpers import REPO_ROOT, write_executable


def test_claude_entrypoint_runs_with_custom_message(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "claude.argv"
    write_executable(
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
    write_executable(
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
    write_executable(
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
