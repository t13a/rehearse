"""Verify the env-var contract between run.run_agent and the runner script."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from rehearse import config, run, session
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
    "REHEARSE_SESSION_DIR",
    "REHEARSE_AGENT_WORK_DIR",
    "REHEARSE_AGENT_HOME",
    "REHEARSE_SESSION_RUN_LOCK",
    "REHEARSE_SESSION_A",
    "REHEARSE_SESSION_B",
    "REHEARSE_AGENT_IMAGE",
    "REHEARSE_AGENT_UID",
    "REHEARSE_AGENT_GID",
    "REHEARSE_AGENT_TIMEOUT",
    "REHEARSE_RUNNER_MODE",
}


def test_run_agent_passes_required_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    config.reload()
    profile = effective_profile({"agent_runner": str(runner)})

    session_dir = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    session_dir.mkdir()
    a.mkdir()
    b.mkdir()

    run_lock_path = session.run_lock_path(session_dir)

    rc = run.run_agent(session_dir, a, b, profile, run_lock_path=run_lock_path)
    assert rc == 0

    env = _parse_env(dump)

    missing = REQUIRED_KEYS - env.keys()
    assert not missing, f"runner did not receive: {missing}"

    assert env["REHEARSE_SESSION_DIR"] == str(session_dir)
    assert env["REHEARSE_AGENT_WORK_DIR"] == str(session_dir / "work")
    assert env["REHEARSE_AGENT_HOME"] == str(session_dir / "home" / "agent")
    assert env["REHEARSE_SESSION_RUN_LOCK"] == str(run_lock_path)
    assert env["REHEARSE_SESSION_A"] == str(a)
    assert env["REHEARSE_SESSION_B"] == str(b)
    assert env["REHEARSE_AGENT_IMAGE"] == config.DEFAULT_CODEX_AGENT_IMAGE
    assert env["REHEARSE_AGENT_UID"] == str(config.DEFAULT_AGENT_UID)
    assert env["REHEARSE_AGENT_GID"] == str(config.DEFAULT_AGENT_GID)
    assert env["REHEARSE_AGENT_TIMEOUT"] == str(config.DEFAULT_AGENT_TIMEOUT)
    assert env["REHEARSE_RUNNER_MODE"] == "run"

    config.reload()


def test_run_agent_passes_message_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    config.reload()
    profile = effective_profile({"agent_runner": str(runner)})

    session_dir = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    session_dir.mkdir()
    a.mkdir()
    b.mkdir()

    rc = run.run_agent(
        session_dir,
        a,
        b,
        profile,
        run_lock_path=session.run_lock_path(session_dir),
        message="追加指示テスト",
    )
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

    session_dir = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    session_dir.mkdir()
    a.mkdir()
    b.mkdir()

    rc = run.run_agent(
        session_dir, a, b, profile, run_lock_path=session.run_lock_path(session_dir)
    )
    assert rc == 0

    env = _parse_env(dump)
    assert "REHEARSE_AGENT_MESSAGE" not in env

    config.reload()


def test_run_agent_passes_extra_args_when_set(tmp_path: Path) -> None:
    dump = tmp_path / "env.dump"
    runner = _make_dump_runner(tmp_path, dump)

    profile = effective_profile(
        {"agent_runner": str(runner), "agent_extra_args": "--verbose"}
    )

    session_dir = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    session_dir.mkdir()
    a.mkdir()
    b.mkdir()

    rc = run.run_agent(
        session_dir, a, b, profile, run_lock_path=session.run_lock_path(session_dir)
    )
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

    session_dir = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    session_dir.mkdir()
    a.mkdir()
    b.mkdir()

    rc = run.run_agent(
        session_dir, a, b, profile, run_lock_path=session.run_lock_path(session_dir)
    )
    assert rc == 7

    config.reload()


def test_run_debug_passes_entrypoint_and_args(tmp_path: Path) -> None:
    dump = tmp_path / "env.dump"
    runner = tmp_path / "dump-runner.sh"
    runner.write_text(
        "#!/bin/bash\n"
        f"env > {dump}.env\n"
        f"printf '%s\\n' \"$@\" > {dump}.argv\n"
    )
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    profile = effective_profile({"agent_runner": str(runner)})

    session_dir = tmp_path / "ws"
    a = tmp_path / "A"
    b = tmp_path / "B"
    session_dir.mkdir()
    a.mkdir()
    b.mkdir()

    rc = run.run_debug(
        session_dir,
        a,
        b,
        profile,
        run_lock_path=session.run_lock_path(session_dir),
        argv=["/bin/bash", "-lc", "id"],
    )
    assert rc == 0

    env = _parse_env(Path(f"{dump}.env"))
    argv = Path(f"{dump}.argv").read_text().splitlines()
    assert env["REHEARSE_RUNNER_MODE"] == "debug"
    assert env["REHEARSE_DEBUG_ENTRYPOINT"] == "/bin/bash"
    assert "REHEARSE_AGENT_MESSAGE" not in env
    assert argv == ["-lc", "id"]
