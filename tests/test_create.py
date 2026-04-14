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

    assert (data / "refs" / "a").is_symlink()
    assert (data / "refs" / "b").is_symlink()
    assert (data / "refs" / "a").resolve() == a.resolve()
    assert (data / "refs" / "b").resolve() == b.resolve()

    # inbox/ mirrors A
    assert (data / "inbox" / "file1.txt").is_symlink()
    assert (data / "inbox" / "sub" / "file2.txt").is_symlink()

    # outbox/ mirrors B
    assert (data / "outbox" / "existing" / "old.txt").is_symlink()

    # inbox/ symlink target points via data/refs/a/...
    inbox_link = data / "inbox" / "file1.txt"
    target = os.readlink(inbox_link)
    assert target == str(data / "refs" / "a" / "file1.txt")

    # outbox/ and subdirs are sticky (mode 1777)
    d_mode = stat.S_IMODE(os.stat(data / "outbox").st_mode)
    assert d_mode == 0o1777
    sub_mode = stat.S_IMODE(os.stat(data / "outbox" / "existing").st_mode)
    assert sub_mode == 0o1777

    # inbox/ symlinks owned by agent UID after chown handoff
    c_stat = os.lstat(inbox_link)
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
