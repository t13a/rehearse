"""Verify the env-var contract between docker.run_agent and the runner script."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from rehearse import config, docker
from rehearse.profile import effective_profile


def _make_dump_runner(tmp_path: Path, dump_path: Path) -> Path:
    """A tiny bash script that writes its env to dump_path and exits 0."""
    runner = tmp_path / "dump-runner.sh"
    runner.write_text(
        "#!/bin/bash\n"
        f"env > {dump_path}\n"
        "exit 0\n"
    )
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return runner


def _parse_env(dump_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in dump_path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


REQUIRED_KEYS = {
    "REHEARSE_SESSION_WORKSPACE",
    "REHEARSE_SESSION_DATA",
    "REHEARSE_SESSION_HOME",
    "REHEARSE_SESSION_RUN_LOCK",
    "REHEARSE_SESSION_A",
    "REHEARSE_SESSION_B",
    "REHEARSE_AGENT_IMAGE",
    "REHEARSE_AGENT_UID",
    "REHEARSE_AGENT_GID",
    "REHEARSE_AGENT_TIMEOUT",
}


def test_run_agent_passes_required_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    config.reload()
    profile = effective_profile({"agent_runner": str(runner)})

    workspace = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    workspace.mkdir()
    a.mkdir()
    b.mkdir()

    rc = docker.run_agent(workspace, a, b, profile)
    assert rc == 0

    env = _parse_env(dump)

    missing = REQUIRED_KEYS - env.keys()
    assert not missing, f"runner did not receive: {missing}"

    assert env["REHEARSE_SESSION_WORKSPACE"] == str(workspace)
    assert env["REHEARSE_SESSION_DATA"] == str(workspace / "data")
    assert env["REHEARSE_SESSION_HOME"] == str(workspace / "home" / "agent")
    assert env["REHEARSE_SESSION_RUN_LOCK"] == str(workspace / "run.lock")
    assert env["REHEARSE_SESSION_A"] == str(a)
    assert env["REHEARSE_SESSION_B"] == str(b)
    assert env["REHEARSE_AGENT_IMAGE"] == config.DEFAULT_AGENT_IMAGE
    assert env["REHEARSE_AGENT_UID"] == str(config.DEFAULT_AGENT_UID)
    assert env["REHEARSE_AGENT_GID"] == str(config.DEFAULT_AGENT_GID)
    assert env["REHEARSE_AGENT_TIMEOUT"] == str(config.DEFAULT_AGENT_TIMEOUT)
    assert "REHEARSE_MCP_CONFIG" not in env

    config.reload()


def test_run_agent_passes_message_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    config.reload()
    profile = effective_profile({"agent_runner": str(runner)})

    workspace = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    workspace.mkdir()
    a.mkdir()
    b.mkdir()

    rc = docker.run_agent(workspace, a, b, profile, message="追加指示テスト")
    assert rc == 0

    env = _parse_env(dump)
    assert env.get("REHEARSE_AGENT_MESSAGE") == "追加指示テスト"

    config.reload()


def test_run_agent_omits_message_when_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    config.reload()
    profile = effective_profile({"agent_runner": str(runner)})

    workspace = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    workspace.mkdir()
    a.mkdir()
    b.mkdir()

    rc = docker.run_agent(workspace, a, b, profile)
    assert rc == 0

    env = _parse_env(dump)
    assert "REHEARSE_AGENT_MESSAGE" not in env

    config.reload()


def test_run_agent_passes_extra_args_when_set(
    tmp_path: Path,
) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    profile = effective_profile(
        {"agent_runner": str(runner), "agent_extra_args": "--verbose"}
    )

    workspace = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    workspace.mkdir()
    a.mkdir()
    b.mkdir()

    rc = docker.run_agent(workspace, a, b, profile)
    assert rc == 0

    env = _parse_env(dump)
    assert env["REHEARSE_AGENT_EXTRA_ARGS"] == "--verbose"


def test_run_agent_propagates_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = tmp_path / "fail-runner.sh"
    runner.write_text("#!/bin/bash\nexit 7\n")
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    config.reload()
    profile = effective_profile({"agent_runner": str(runner)})

    workspace = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    workspace.mkdir()
    a.mkdir()
    b.mkdir()

    rc = docker.run_agent(workspace, a, b, profile)
    assert rc == 7

    config.reload()
