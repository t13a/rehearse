"""End-to-end lifecycle test: create → run → discard → purge + stubs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rehearse import commands, config
from rehearse.meta import SessionStatus, read_meta, write_meta


pytestmark = pytest.mark.docker


def _hash_tree(root: Path) -> str:
    """Hash of (relpath, content) pairs for regular files under `root`.

    Used to check that discard / purge / run do NOT mutate A or B.
    """
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            h.update(str(path.relative_to(root)).encode())
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def test_full_lifecycle(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    a_hash_before = _hash_tree(a)
    b_hash_before = _hash_tree(b)

    # create
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    # status (listing)
    assert commands.cmd_status(None) == 0
    listing = capsys.readouterr().out
    assert session_id in listing
    assert "created" in listing

    # run
    assert commands.cmd_run(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done
    assert (session_dir / "data" / "d" / ".done").exists()

    # status (detail)
    assert commands.cmd_status(session_id) == 0
    detail = capsys.readouterr().out
    assert '"status": "done"' in detail

    # commit — fake runner doesn't move c/ into d/, so this is a no-op
    # (only B-mirror symlinks in d/, all skipped). A and B stay untouched.
    assert commands.cmd_commit(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.committed

    assert _hash_tree(a) == a_hash_before
    assert _hash_tree(b) == b_hash_before

    # purge
    assert commands.cmd_purge(session_id) == 0
    assert not session_dir.exists()


def test_cannot_purge_running_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    # Forcibly mark as running without actually running.
    meta = read_meta(session_dir)
    meta.status = SessionStatus.running
    write_meta(session_dir, meta)

    assert commands.cmd_purge(session_id) == 2
    err = capsys.readouterr().err
    assert "running" in err

    # reset so teardown can clean up
    meta.status = SessionStatus.failed
    write_meta(session_dir, meta)


def test_run_from_done_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A done session can be re-run (the agent resumes automatically)."""
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    # First run
    assert commands.cmd_run(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done

    # Second run from done
    assert commands.cmd_run(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done


def test_run_with_message(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The -m flag is accepted on any run."""
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()

    assert commands.cmd_run(session_id, message="テスト指示") == 0
