"""Tests for session directory lifecycle."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from rehearse import config, session
from rehearse.session import SessionStatus
from rehearse.session import read_meta


@pytest.mark.docker
def test_create_session_with_no_options(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))

    session_dir = config.SESSIONS_DIR / session_id
    work = session_dir / "work"

    assert (work / "refs" / "a").is_symlink()
    assert (work / "refs" / "b").is_symlink()
    assert (work / "refs" / "a").resolve() == a.resolve()
    assert (work / "refs" / "b").resolve() == b.resolve()

    assert (work / "inbox" / "file1.txt").is_symlink()
    assert (work / "inbox" / "sub" / "file2.txt").is_symlink()
    assert (work / "outbox" / "existing" / "old.txt").is_symlink()

    assert (work / "AGENTS.md").is_file()
    assert (work / "AGENTS.md").read_text() == config.DEFAULT_AGENT_INSTRUCTIONS.read_text()
    assert (work / "CLAUDE.md").is_symlink()
    assert os.readlink(work / "CLAUDE.md") == "AGENTS.md"

    inbox_link = work / "inbox" / "file1.txt"
    target = os.readlink(inbox_link)
    assert target == str(work / "refs" / "a" / "file1.txt")

    d_mode = stat.S_IMODE(os.stat(work / "outbox").st_mode)
    assert d_mode == 0o1777
    sub_mode = stat.S_IMODE(os.stat(work / "outbox" / "existing").st_mode)
    assert sub_mode == 0o1777

    work_stat = os.lstat(work)
    assert work_stat.st_uid == config.DEFAULT_GUARD_UID
    assert work_stat.st_gid == config.DEFAULT_GUARD_GID
    outbox_link_stat = os.lstat(work / "outbox" / "existing" / "old.txt")
    assert outbox_link_stat.st_uid == config.DEFAULT_GUARD_UID
    assert outbox_link_stat.st_gid == config.DEFAULT_GUARD_GID
    agents_stat = os.lstat(work / "AGENTS.md")
    assert agents_stat.st_uid == config.DEFAULT_GUARD_UID
    assert agents_stat.st_gid == config.DEFAULT_GUARD_GID
    claude_stat = os.lstat(work / "CLAUDE.md")
    assert claude_stat.st_uid == config.DEFAULT_GUARD_UID
    assert claude_stat.st_gid == config.DEFAULT_GUARD_GID

    c_stat = os.lstat(inbox_link)
    assert c_stat.st_uid == config.DEFAULT_AGENT_UID
    assert c_stat.st_gid == config.DEFAULT_AGENT_GID

    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.created
    assert meta.session_id == session_id
    assert meta.a == a.resolve()
    assert meta.b == b.resolve()
    assert meta.profile_name == "default"
    assert meta.profile["agent_image"] == "busybox:latest"

    assert (session_dir / ".git").is_dir()
    tracked = subprocess.run(
        ["git", "-C", str(session_dir), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert "work/AGENTS.md" in tracked
    assert "work/CLAUDE.md" in tracked


@pytest.mark.docker
def test_create_session_with_options(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    skel = config.SKELETONS_DIR / "custom_skeleton"
    skel.mkdir(parents=True)
    (skel / "marker.txt").write_text("custom skeleton\n")

    custom = config.PROFILES_DIR / "custom_profile.json"
    custom.write_text('{"skeleton": "custom_skeleton"}\n')

    session_id = session.create_session(
        str(a), str(b), profile_name="custom_profile", session_id="custom_session"
    )

    assert session_id == "custom_session"
    session_dir = config.SESSIONS_DIR / "custom_session"
    agent_home = session_dir / "home" / "agent"

    assert session_dir.is_dir()
    assert (agent_home / "marker.txt").read_text() == "custom skeleton\n"

    marker_stat = os.lstat(agent_home / "marker.txt")
    assert marker_stat.st_uid == config.DEFAULT_AGENT_UID
    assert marker_stat.st_gid == config.DEFAULT_AGENT_GID

    meta = read_meta(session_dir)
    assert meta.session_id == "custom_session"
    assert meta.profile_name == "custom_profile"
    assert meta.profile == {"skeleton": "custom_skeleton"}

    tracked = subprocess.run(
        ["git", "-C", str(session_dir), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "home/agent/marker.txt" not in tracked


@pytest.mark.parametrize("session_id", ["", "../bad", "bad/name", "bad name", ".", ".."])
def test_create_session_rejects_invalid_session_id(
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    session_id: str,
) -> None:
    a, b = fake_ab

    with pytest.raises(session.SessionIdError, match="invalid session id"):
        session.create_session(str(a), str(b), session_id=session_id)


def test_create_session_rejects_existing_session_id(
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    existing = config.SESSIONS_DIR / "taken"
    existing.mkdir(parents=True)

    with pytest.raises(session.SessionIdError, match="session already exists: taken"):
        session.create_session(str(a), str(b), session_id="taken")
    assert list(existing.iterdir()) == []


@pytest.mark.docker
def test_create_session_guards_b_mirror_from_agent(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    if config.DEFAULT_AGENT_UID == 0:
        pytest.skip("root can bypass sticky bit ownership checks")

    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    work = config.SESSIONS_DIR / session_id / "work"

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--user", f"{config.DEFAULT_AGENT_UID}:{config.DEFAULT_AGENT_GID}",
            "-v", f"{work}:{work}:rw",
            "busybox:latest",
            "mv",
            str(work / "outbox" / "existing" / "old.txt"),
            str(work / "outbox" / "existing" / "renamed.txt"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert (work / "outbox" / "existing" / "old.txt").is_symlink()
    assert not (work / "outbox" / "existing" / "renamed.txt").exists()
