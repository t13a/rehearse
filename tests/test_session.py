"""Tests for session workspace lifecycle."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from rehearse import config, profile, session, validate, workspace
from rehearse.session import SessionStatus
from rehearse.session import read_meta


@pytest.mark.docker
def test_create_builds_workspace(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))

    session_dir = config.SESSIONS_DIR / session_id
    data = session_dir / "data"

    assert (data / "refs" / "a").is_symlink()
    assert (data / "refs" / "b").is_symlink()
    assert (data / "refs" / "a").resolve() == a.resolve()
    assert (data / "refs" / "b").resolve() == b.resolve()

    assert (data / "inbox" / "file1.txt").is_symlink()
    assert (data / "inbox" / "sub" / "file2.txt").is_symlink()
    assert (data / "outbox" / "existing" / "old.txt").is_symlink()

    assert (data / "AGENTS.md").is_file()
    assert (data / "AGENTS.md").read_text() == config.DEFAULT_AGENT_INSTRUCTIONS.read_text()
    assert (data / "CLAUDE.md").is_symlink()
    assert os.readlink(data / "CLAUDE.md") == "AGENTS.md"

    inbox_link = data / "inbox" / "file1.txt"
    target = os.readlink(inbox_link)
    assert target == str(data / "refs" / "a" / "file1.txt")

    d_mode = stat.S_IMODE(os.stat(data / "outbox").st_mode)
    assert d_mode == 0o1777
    sub_mode = stat.S_IMODE(os.stat(data / "outbox" / "existing").st_mode)
    assert sub_mode == 0o1777

    data_stat = os.lstat(data)
    assert data_stat.st_uid == config.DEFAULT_GUARD_UID
    assert data_stat.st_gid == config.DEFAULT_GUARD_GID
    outbox_link_stat = os.lstat(data / "outbox" / "existing" / "old.txt")
    assert outbox_link_stat.st_uid == config.DEFAULT_GUARD_UID
    assert outbox_link_stat.st_gid == config.DEFAULT_GUARD_GID
    agents_stat = os.lstat(data / "AGENTS.md")
    assert agents_stat.st_uid == config.DEFAULT_GUARD_UID
    assert agents_stat.st_gid == config.DEFAULT_GUARD_GID
    claude_stat = os.lstat(data / "CLAUDE.md")
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
    assert "data/AGENTS.md" in tracked
    assert "data/CLAUDE.md" in tracked


@pytest.mark.docker
def test_create_uses_named_profile(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    custom = config.PROFILES_DIR / "custom.json"
    custom.write_text('{"agent_image": "busybox:latest", "agent_timeout": 42}\n')

    session_id = session.create_session(str(a), str(b), profile_name="custom")
    meta = read_meta(config.SESSIONS_DIR / session_id)

    assert meta.profile_name == "custom"
    assert meta.profile == {"agent_image": "busybox:latest", "agent_timeout": 42}


@pytest.mark.docker
def test_create_uses_named_session_id(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab

    session_id = session.create_session(str(a), str(b), session_id="safe_1.2-3")

    assert session_id == "safe_1.2-3"
    session_dir = config.SESSIONS_DIR / "safe_1.2-3"
    assert session_dir.is_dir()
    assert read_meta(session_dir).session_id == "safe_1.2-3"


@pytest.mark.parametrize("session_id", ["", "../bad", "bad/name", "bad name", ".", ".."])
def test_create_rejects_invalid_named_session_id(
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    session_id: str,
) -> None:
    a, b = fake_ab

    with pytest.raises(workspace.SessionIdError, match="invalid session id"):
        session.create_session(str(a), str(b), session_id=session_id)


def test_create_rejects_existing_named_session_id(
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    existing = config.SESSIONS_DIR / "taken"
    existing.mkdir(parents=True)

    with pytest.raises(workspace.SessionIdError, match="session already exists: taken"):
        session.create_session(str(a), str(b), session_id="taken")
    assert list(existing.iterdir()) == []


@pytest.mark.docker
def test_create_copies_named_skeleton(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    skel = config.SKELETONS_DIR / "codex"
    (skel / ".codex").mkdir(parents=True)
    (skel / ".codex" / "auth.json").write_text('{"token": "secret"}\n')
    (skel / ".codex" / "config.toml").write_text("model = 'gpt-5.4'\n")
    (skel / "auth-link").symlink_to(".codex/auth.json")

    custom = config.PROFILES_DIR / "codex.json"
    custom.write_text('{"skeleton": "codex"}\n')

    session_id = session.create_session(str(a), str(b), profile_name="codex")

    session_dir = config.SESSIONS_DIR / session_id
    agent_home = session_dir / "home" / "agent"

    assert (agent_home / ".codex" / "auth.json").read_text() == '{"token": "secret"}\n'
    assert (agent_home / ".codex" / "config.toml").exists()
    assert (agent_home / "auth-link").is_symlink()
    assert os.readlink(agent_home / "auth-link") == ".codex/auth.json"

    copied_stat = os.lstat(agent_home / ".codex" / "auth.json")
    assert copied_stat.st_uid == config.DEFAULT_AGENT_UID
    assert copied_stat.st_gid == config.DEFAULT_AGENT_GID

    meta = read_meta(session_dir)
    assert meta.profile == {"skeleton": "codex"}

    tracked = subprocess.run(
        ["git", "-C", str(session_dir), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "home/agent/.codex/auth.json" not in tracked

    (skel / ".codex" / "auth.json").write_text('{"token": "changed-source"}\n')
    assert (agent_home / ".codex" / "auth.json").read_text() == '{"token": "secret"}\n'
    subprocess.run(
        [
            "docker", "run", "--rm",
            "--user", f"{config.DEFAULT_AGENT_UID}:{config.DEFAULT_AGENT_GID}",
            "-v", f"{agent_home}:{agent_home}:rw",
            "busybox:latest",
            "sh", "-c",
            f"printf '%s\\n' '{{\"token\": \"changed-session\"}}' > {agent_home / '.codex' / 'auth.json'}",
        ],
        check=True,
    )
    assert (skel / ".codex" / "auth.json").read_text() == '{"token": "changed-source"}\n'


@pytest.mark.docker
def test_create_guard_owned_b_mirror_rejects_agent_rename(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    if config.DEFAULT_AGENT_UID == 0:
        pytest.skip("root can bypass sticky bit ownership checks")

    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    data = config.SESSIONS_DIR / session_id / "data"

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--user", f"{config.DEFAULT_AGENT_UID}:{config.DEFAULT_AGENT_GID}",
            "-v", f"{data}:{data}:rw",
            "busybox:latest",
            "mv",
            str(data / "outbox" / "existing" / "old.txt"),
            str(data / "outbox" / "existing" / "renamed.txt"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert (data / "outbox" / "existing" / "old.txt").is_symlink()
    assert not (data / "outbox" / "existing" / "renamed.txt").exists()


@pytest.mark.docker
def test_create_auto_creates_default_skeleton(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    default = config.SKELETONS_DIR / "default"
    assert not default.exists()

    session.create_session(str(a), str(b))

    assert default.is_dir()


@pytest.mark.docker
def test_create_copies_custom_agent_instructions(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    instructions = config.REHEARSE_ROOT / "instructions" / "custom.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# Custom instructions\n")
    custom = config.PROFILES_DIR / "custom-instructions.json"
    custom.write_text('{"agent_instructions": "instructions/custom.md"}\n')

    session_id = session.create_session(
        str(a), str(b), profile_name="custom-instructions"
    )

    data = config.SESSIONS_DIR / session_id / "data"
    assert (data / "AGENTS.md").read_text() == "# Custom instructions\n"

    instructions.write_text("# Changed instructions\n")
    assert (data / "AGENTS.md").read_text() == "# Custom instructions\n"


def test_create_rejects_missing_profile(
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab

    with pytest.raises(profile.ProfileError, match="profile not found"):
        session.create_session(str(a), str(b), profile_name="missing")


def test_create_rejects_missing_skeleton(
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    custom = config.PROFILES_DIR / "missing-skeleton.json"
    custom.write_text('{"skeleton": "ghost"}\n')

    with pytest.raises(profile.ProfileError, match="skeleton not found"):
        session.create_session(str(a), str(b), profile_name="missing-skeleton")


def test_create_rejects_preflight_errors(
    rehearse_root: Path,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    b = tmp_path / "B"
    b.mkdir()

    with pytest.raises(validate.PreflightError, match="A does not exist"):
        session.create_session(str(missing), str(b))
