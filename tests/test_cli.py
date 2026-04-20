"""CLI controller tests: create -> run/debug -> commit -> delete."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rehearse import cli, config, lock, run, session
from rehearse.session import SessionStatus
from rehearse.session import read_meta, write_meta


pytestmark = pytest.mark.docker


def _hash_tree(root: Path) -> str:
    """Hash of (relpath, content) pairs for regular files under `root`."""
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

    assert cli.main(["create", str(a), str(b)]) == 0
    session_id = capsys.readouterr().out.strip()
    session_dir = config.SESSIONS_DIR / session_id

    assert cli.main(["status"]) == 0
    listing = capsys.readouterr().out
    assert session_id in listing
    assert "created" in listing

    (config.PROFILES_DIR / "default.json").write_text(
        '{"agent_runner": "/does/not/exist", "agent_image": "missing:latest"}\n'
    )
    assert cli.main(["run", session_id]) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done
    assert (session_dir / "work" / "outbox" / ".done").exists()

    assert cli.main(["status", session_id]) == 0
    detail = capsys.readouterr().out
    assert '"status": "done"' in detail

    assert cli.main(["commit", session_id]) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.committed

    assert _hash_tree(a) == a_hash_before
    assert _hash_tree(b) == b_hash_before

    assert cli.main(["delete", session_id]) == 0
    assert not session_dir.exists()


def test_cannot_delete_locked_running_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    with lock.flock_exclusive(session.run_lock_path(session_dir)):
        assert cli.main(["delete", session_id]) == 2
    err = capsys.readouterr().err
    assert "running" in err


def test_status_reports_locked_session_as_running(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    meta = read_meta(session_dir)
    meta.status = SessionStatus.done
    write_meta(session_dir, meta)

    with lock.flock_exclusive(session.run_lock_path(session_dir)):
        assert cli.main(["status", session_id]) == 0
    detail = capsys.readouterr().out
    assert '"status": "running"' in detail

    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done


def test_interrupted_run_does_not_persist_running_status(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    def interrupt(*args: object, **kwargs: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "run_agent", interrupt)

    with pytest.raises(KeyboardInterrupt):
        cli.main(["run", session_id])

    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.failed
    assert meta.started_at is not None
    assert meta.ended_at is None
    assert meta.exit_reason == "interrupted"


def test_run_from_done_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    assert cli.main(["run", session_id]) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done

    assert cli.main(["run", session_id]) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done


def test_run_with_message(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    assert cli.main(["run", session_id, "-m", "テスト指示"]) == 0
    assert (session_dir / "work" / "outbox" / "FYI.md").read_text() == "テスト指示\n"


def test_debug_requires_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["debug", "session"]) == 2
    assert "usage: rehearse debug" in capsys.readouterr().err


def test_debug_uses_run_status_flow(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    def fake_debug(
        session_dir_arg: Path,
        _a: Path,
        _b: Path,
        _profile: object,
        *,
        run_lock_path: Path,
        argv: list[str],
    ) -> int:
        assert session_dir_arg == session_dir
        assert run_lock_path == session.run_lock_path(session_dir)
        assert argv == ["/bin/bash", "-lc", "touch outbox/.done"]
        (session_dir_arg / "work" / "outbox" / ".done").touch()
        return 0

    monkeypatch.setattr(run, "run_debug", fake_debug)

    assert cli.main(["debug", session_id, "/bin/bash", "-lc", "touch outbox/.done"]) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.done
    assert meta.started_at is not None
    assert meta.ended_at is not None
    assert meta.exit_reason == "normal"


def test_debug_rejects_locked_running_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    with lock.flock_exclusive(session.run_lock_path(session_dir)):
        assert cli.main(["debug", session_id, "/bin/bash"]) == 2
    err = capsys.readouterr().err
    assert "cannot debug session in status=running" in err


def test_commit_rejects_locked_running_session(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    meta = read_meta(session_dir)
    meta.status = SessionStatus.done
    write_meta(session_dir, meta)

    with lock.flock_exclusive(session.run_lock_path(session_dir)):
        assert cli.main(["commit", session_id]) == 2
    assert "running" in capsys.readouterr().err

    meta = read_meta(session_dir)
    meta.status = SessionStatus.failed
    write_meta(session_dir, meta)


def test_commit_transitions_to_committed(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    meta = read_meta(session_dir)
    meta.status = SessionStatus.done
    write_meta(session_dir, meta)

    assert cli.main(["commit", session_id]) == 0
    meta = read_meta(session_dir)
    assert meta.status == SessionStatus.committed


def test_exec_runs_in_work_dir(
    docker_available: bool,
    rehearse_root: Path,
    fake_ab: tuple[Path, Path],
) -> None:
    a, b = fake_ab
    session_id = session.create_session(str(a), str(b))
    session_dir = config.SESSIONS_DIR / session_id

    out = session_dir / "work" / "outbox" / "cwd.txt"
    assert cli.main(["exec", session_id, "sh", "-c", f"pwd > {out}"]) == 0
    assert out.read_text().strip() == str(session_dir / "work")
