"""End-to-end lifecycle test: create → run → commit → purge + stubs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rehearse import commands, config, workspace
from rehearse.meta import SessionStatus, meta_path, read_meta, write_meta


pytestmark = pytest.mark.docker


def _hash_tree(root: Path) -> str:
    """Hash of (relpath, content) pairs for regular files under `root`.

    Used to check that purge / run do NOT mutate A or B.
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
    (config.PROFILES_DIR / "default.json").write_text(
        '{"agent_runner": "/does/not/exist", "agent_image": "missing:latest"}\n'
    )
    assert commands.cmd_run(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done
    assert (session_dir / "data" / "outbox" / ".done").exists()

    # status (detail)
    assert commands.cmd_status(session_id) == 0
    detail = capsys.readouterr().out
    assert '"status": "done"' in detail

    # commit — fake runner doesn't move inbox/ into outbox/, so this is a no-op
    # (only B-mirror symlinks in outbox/, all skipped). A and B stay untouched.
    assert commands.cmd_commit(session_id) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.committed

    assert _hash_tree(a) == a_hash_before
    assert _hash_tree(b) == b_hash_before

    # purge
    assert commands.cmd_purge(session_id) == 0
    assert not session_dir.exists()


def test_cannot_purge_locked_running_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    with workspace.flock_exclusive(workspace.run_lock_path(session_dir)):
        assert commands.cmd_purge(session_id) == 2
    err = capsys.readouterr().err
    assert "running" in err


def test_status_rejects_persisted_running_status(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    raw = meta_path(session_dir).read_text()
    meta_path(session_dir).write_text(
        raw.replace('"status": "created"', '"status": "running"')
    )

    with pytest.raises(ValueError, match="status=running must not be persisted"):
        commands.cmd_status(session_id)

    meta_path(session_dir).write_text(raw)


def test_status_reports_locked_session_as_running(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    meta = read_meta(session_dir)
    meta.status = SessionStatus.done
    write_meta(session_dir, meta)

    with workspace.flock_exclusive(workspace.run_lock_path(session_dir)):
        assert commands.cmd_status(session_id) == 0
    detail = capsys.readouterr().out
    assert '"status": "running"' in detail

    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done


def test_interrupted_run_does_not_persist_running_status(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    def interrupt(*args: object, **kwargs: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(commands.docker, "run_agent", interrupt)

    with pytest.raises(KeyboardInterrupt):
        commands.cmd_run(session_id)

    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.failed
    assert meta.started_at is not None
    assert meta.ended_at is None
    assert meta.exit_reason == "interrupted"


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


def test_exec_runs_in_data_dir(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    assert commands.cmd_create(str(a), str(b)) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    out = session_dir / "data" / "outbox" / "cwd.txt"
    assert commands.cmd_exec(session_id, ["sh", "-c", f"pwd > {out}"]) == 0
    assert out.read_text().strip() == str(session_dir / "data")
