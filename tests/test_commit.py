"""Tests for the commit algorithm and cmd_commit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rehearse import commands, commit, config, mirror
from rehearse.meta import SessionStatus, read_meta, write_meta


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _build_workspace(tmp_path: Path, a: Path, b: Path) -> Path:
    """Build a minimal workspace (no docker, no chown) for commit testing."""
    session_dir = tmp_path / "session"
    data_dir = session_dir / "data"
    data_dir.mkdir(parents=True)
    mirror.build_workspace_data(data_dir, a, b)
    return session_dir


def _read_log_ops(session_dir: Path) -> list[str]:
    log = session_dir / "commit.log"
    if not log.exists():
        return []
    return [json.loads(line)["op"] for line in log.read_text().splitlines()]


# ---------------------------------------------------------------------------
# pure-logic tests (no docker)
# ---------------------------------------------------------------------------

def test_commit_moves_a_files(tmp_path: Path, fake_ab: tuple[Path, Path]) -> None:
    a, b = fake_ab
    session_dir = _build_workspace(tmp_path, a, b)
    outbox = session_dir / "data" / "outbox"

    # Simulate agent moving inbox/file1.txt → outbox/newdir/file1.txt
    src_link = session_dir / "data" / "inbox" / "file1.txt"
    dst_dir = outbox / "newdir"
    dst_dir.mkdir()
    src_link.rename(dst_dir / "file1.txt")

    stats = commit.commit_session(session_dir, a, b)

    assert stats.moved == 1
    assert stats.inbox_remaining == 1  # sub/file2.txt still in inbox
    assert not (a / "file1.txt").exists()
    assert (b / "newdir" / "file1.txt").exists()
    assert (b / "newdir" / "file1.txt").read_text() == "hello\n"
    assert "moved" in _read_log_ops(session_dir)


def test_commit_is_idempotent(tmp_path: Path, fake_ab: tuple[Path, Path]) -> None:
    a, b = fake_ab
    session_dir = _build_workspace(tmp_path, a, b)
    outbox = session_dir / "data" / "outbox"

    src_link = session_dir / "data" / "inbox" / "file1.txt"
    dst_dir = outbox / "placed"
    dst_dir.mkdir()
    src_link.rename(dst_dir / "file1.txt")

    s1 = commit.commit_session(session_dir, a, b)
    assert s1.moved == 1

    s2 = commit.commit_session(session_dir, a, b)
    assert s2.moved == 0
    assert s2.already_moved == 1
    assert (b / "placed" / "file1.txt").read_text() == "hello\n"


def test_commit_skips_initial_b_symlinks(
    tmp_path: Path, fake_ab: tuple[Path, Path]
) -> None:
    a, b = fake_ab
    session_dir = _build_workspace(tmp_path, a, b)

    # Don't move anything — commit sees only B-mirror symlinks
    stats = commit.commit_session(session_dir, a, b)

    assert stats.moved == 0
    assert stats.skipped_b == 1  # b/existing/old.txt
    assert stats.inbox_remaining == 2  # file1.txt + sub/file2.txt still alive
    assert (a / "file1.txt").exists()
    assert (b / "existing" / "old.txt").read_text() == "legacy\n"


def test_commit_skips_fyi_files(
    tmp_path: Path, fake_ab: tuple[Path, Path]
) -> None:
    a, b = fake_ab
    session_dir = _build_workspace(tmp_path, a, b)
    outbox = session_dir / "data" / "outbox"

    # Add a .FYI.md as a real file
    (outbox / "note.FYI.md").write_text("Some notes\n")

    # Also move an A-origin file
    src_link = session_dir / "data" / "inbox" / "file1.txt"
    src_link.rename(outbox / "file1.txt")

    stats = commit.commit_session(session_dir, a, b)

    assert stats.skipped_file >= 1
    assert stats.moved == 1
    # .FYI.md should NOT appear in B
    assert not (b / "note.FYI.md").exists()
    # .FYI.md stays in outbox/
    assert (outbox / "note.FYI.md").exists()


def test_commit_aborts_on_conflict(
    tmp_path: Path, fake_ab: tuple[Path, Path]
) -> None:
    a, b = fake_ab
    # Pre-create a collision file in B
    (b / "collision").mkdir()
    (b / "collision" / "file1.txt").write_text("I was here first\n")

    # Rebuild workspace so b-mirror picks up the collision dir
    session_dir = _build_workspace(tmp_path, a, b)
    outbox = session_dir / "data" / "outbox"

    # Agent moves inbox/file1.txt → outbox/collision/file1.txt (same name as B's existing)
    src_link = session_dir / "data" / "inbox" / "file1.txt"
    src_link.rename(outbox / "collision" / "file1.txt")

    with pytest.raises(commit.CommitAbort, match="both src and dst"):
        commit.commit_session(session_dir, a, b)

    # A side is untouched
    assert (a / "file1.txt").exists()
    assert "conflict" in _read_log_ops(session_dir)


def test_commit_creates_nested_b_dirs(
    tmp_path: Path, fake_ab: tuple[Path, Path]
) -> None:
    a, b = fake_ab
    session_dir = _build_workspace(tmp_path, a, b)
    outbox = session_dir / "data" / "outbox"

    # Agent places file deep in a path that doesn't exist in B
    deep = outbox / "x" / "y" / "z"
    deep.mkdir(parents=True)
    src_link = session_dir / "data" / "inbox" / "file1.txt"
    src_link.rename(deep / "file1.txt")

    stats = commit.commit_session(session_dir, a, b)

    assert stats.moved == 1
    assert (b / "x" / "y" / "z" / "file1.txt").exists()
    assert (b / "x" / "y" / "z" / "file1.txt").read_text() == "hello\n"


def test_commit_reports_unprocessed(
    tmp_path: Path, fake_ab: tuple[Path, Path]
) -> None:
    a, b = fake_ab
    session_dir = _build_workspace(tmp_path, a, b)
    outbox = session_dir / "data" / "outbox"

    # Move only file1.txt, leave sub/file2.txt in inbox
    src_link = session_dir / "data" / "inbox" / "file1.txt"
    src_link.rename(outbox / "file1.txt")

    stats = commit.commit_session(session_dir, a, b)

    assert stats.moved == 1
    assert stats.inbox_remaining == 1  # sub/file2.txt still in inbox


# ---------------------------------------------------------------------------
# cmd_commit tests (docker required — cmd_create uses chown container)
# ---------------------------------------------------------------------------

@pytest.mark.docker
def test_cmd_commit_rejects_bad_statuses(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    for bad_status in (SessionStatus.created, SessionStatus.running, SessionStatus.discarded):
        meta = read_meta(session_dir)
        meta.status = bad_status
        write_meta(session_dir, meta)
        assert commands.cmd_commit(session_id) == 2

    # Reset for teardown
    meta = read_meta(session_dir)
    meta.status = SessionStatus.failed
    write_meta(session_dir, meta)


@pytest.mark.docker
def test_cmd_commit_transitions_to_committed(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    # Mark as done (fake: no agent ran, but status allows commit)
    meta = read_meta(session_dir)
    meta.status = SessionStatus.done
    write_meta(session_dir, meta)

    assert commands.cmd_commit(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.committed
