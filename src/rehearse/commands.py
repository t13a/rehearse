"""Subcommand implementations for the rehearse CLI."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rehearse import config, docker, mirror, validate, workspace
from rehearse.meta import SessionMeta, SessionStatus, read_meta, write_meta


REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_SNAPSHOT_SCRIPT = REPO_ROOT / "scripts" / "git-snapshot.sh"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_session_dir(session_id: str) -> Path:
    path = workspace.session_path(session_id)
    if not path.exists():
        raise SystemExit(f"session not found: {session_id}")
    return path


# ---- create ------------------------------------------------------------

def cmd_create(a_arg: str, b_arg: str) -> int:
    a = Path(a_arg).resolve()
    b = Path(b_arg).resolve()

    try:
        validate.preflight(a, b)
    except validate.PreflightError as e:
        print(f"preflight failed: {e}", file=sys.stderr)
        return 2

    workspace.ensure_root_dirs()

    with workspace.flock_exclusive(workspace.b_lock_path(b)):
        session_id = workspace.allocate_session_id()
        session_dir = workspace.session_path(session_id)
        data_dir = session_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        mirror.build_workspace_data(data_dir, a, b)

        docker.chown_container(data_dir / "c")

        subprocess.run(
            ["bash", str(GIT_SNAPSHOT_SCRIPT), str(session_dir)],
            check=True,
        )

        meta = SessionMeta(
            session_id=session_id,
            status=SessionStatus.created,
            created_at=_now(),
            a=a,
            b=b,
            workspace=session_dir,
            agent_image=config.REHEARSE_AGENT_IMAGE,
            agent_uid=config.REHEARSE_AGENT_UID,
            agent_gid=config.REHEARSE_AGENT_GID,
        )
        write_meta(session_dir, meta)

    print(session_id)
    return 0


# ---- status ------------------------------------------------------------

def cmd_status(session_id: str | None) -> int:
    if session_id is None:
        sessions = workspace.sessions_dir()
        if not sessions.exists():
            return 0
        rows = []
        for entry in sorted(sessions.iterdir()):
            try:
                meta = read_meta(entry)
                rows.append((meta.session_id, meta.status.value, str(meta.a), str(meta.b)))
            except Exception:
                rows.append((entry.name, "?", "-", "-"))
        for sid, status, a, b in rows:
            print(f"{sid}\t{status}\t{a}\t{b}")
        return 0

    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)
    print(meta.model_dump_json(indent=2))
    return 0


# ---- run ---------------------------------------------------------------

def cmd_run(session_id: str) -> int:
    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)

    if meta.status not in (SessionStatus.created, SessionStatus.failed):
        print(
            f"cannot run session in status={meta.status.value}",
            file=sys.stderr,
        )
        return 2

    meta.status = SessionStatus.running
    meta.started_at = _now()
    write_meta(session_dir, meta)

    rc = docker.run_agent(session_dir, meta.a, meta.b)

    meta.ended_at = _now()
    done_flag = session_dir / "data" / "d" / ".done"
    if rc == 0 and done_flag.exists():
        meta.status = SessionStatus.done
        meta.exit_reason = "normal"
    else:
        meta.status = SessionStatus.failed
        meta.exit_reason = f"exit={rc}" if not done_flag.exists() else "no-done-flag"
    write_meta(session_dir, meta)
    return 0 if meta.status == SessionStatus.done else 1


# ---- discard -----------------------------------------------------------

def cmd_discard(session_id: str) -> int:
    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)
    if meta.status == SessionStatus.running:
        print("cannot discard a running session", file=sys.stderr)
        return 2
    meta.status = SessionStatus.discarded
    write_meta(session_dir, meta)
    return 0


# ---- purge -------------------------------------------------------------

def cmd_purge(session_id: str) -> int:
    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)
    if meta.status == SessionStatus.running:
        print("cannot purge a running session", file=sys.stderr)
        return 2
    docker.cleanup_container(session_dir)
    return 0


# ---- commit (stub) -----------------------------------------------------

def cmd_commit(session_id: str) -> int:
    print("Not implemented yet — will land in Step 4", file=sys.stderr)
    return 1


# ---- resume (stub) -----------------------------------------------------

def cmd_resume(session_id: str) -> int:
    print("Not implemented yet — will land in a later step", file=sys.stderr)
    return 1
