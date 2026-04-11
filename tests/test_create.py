"""Tests for `rehearse create` — workspace layout, permissions, meta.json."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from rehearse import commands, config
from rehearse.meta import SessionStatus, read_meta


pytestmark = pytest.mark.docker


def test_create_builds_workspace(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    rc = commands.cmd_create(str(a), str(b))
    assert rc == 0

    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id
    data = session_dir / "data"

    assert (data / "a").is_symlink()
    assert (data / "b").is_symlink()
    assert (data / "a").resolve() == a.resolve()
    assert (data / "b").resolve() == b.resolve()

    # c/ mirrors A
    assert (data / "c" / "file1.txt").is_symlink()
    assert (data / "c" / "sub" / "file2.txt").is_symlink()

    # d/ mirrors B
    assert (data / "d" / "existing" / "old.txt").is_symlink()

    # c/ symlink target points via data/a/...
    c_link = data / "c" / "file1.txt"
    target = os.readlink(c_link)
    assert target == str(data / "a" / "file1.txt")

    # d/ and subdirs are sticky (mode 1777)
    d_mode = stat.S_IMODE(os.stat(data / "d").st_mode)
    assert d_mode == 0o1777
    sub_mode = stat.S_IMODE(os.stat(data / "d" / "existing").st_mode)
    assert sub_mode == 0o1777

    # c/ symlinks owned by agent UID after chown handoff
    c_stat = os.lstat(c_link)
    assert c_stat.st_uid == config.REHEARSE_AGENT_UID
    assert c_stat.st_gid == config.REHEARSE_AGENT_GID

    # meta.json parses and has created status
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.created
    assert meta.session_id == session_id
    assert meta.a == a.resolve()
    assert meta.b == b.resolve()

    # git snapshot exists
    assert (session_dir / ".git").is_dir()
