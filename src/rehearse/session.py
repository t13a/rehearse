"""Session lifecycle and meta.json helpers."""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator
from rehearse import (
    config,
    helper,
    instruction,
    lock,
    mirror,
    profile as profile_mod,
    skeleton,
    validate,
)
from rehearse.profile import PROFILE_NAME_RE


REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_SNAPSHOT_SCRIPT = REPO_ROOT / "scripts" / "git-snapshot.sh"


class SessionIdError(RuntimeError):
    """Raised when a requested session id is invalid or unavailable."""


class SessionStatus(str, Enum):
    created = "created"
    running = "running"
    done = "done"
    failed = "failed"
    committed = "committed"


class SessionMeta(BaseModel):
    session_id: str
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    a: Path
    b: Path
    session_dir: Path
    profile_name: str
    profile: dict[str, Any]
    exit_reason: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_persisted_session_id(cls, value: str) -> str:
        try:
            validate_session_id(value)
        except SessionIdError as e:
            raise ValueError(str(e)) from e
        return value

    @field_validator("status")
    @classmethod
    def reject_persisted_running(cls, value: SessionStatus) -> SessionStatus:
        if value == SessionStatus.running:
            raise ValueError("status=running must not be persisted")
        return value


def now() -> datetime:
    return datetime.now(timezone.utc)


def meta_path(session_dir: Path) -> Path:
    return session_dir / "meta.json"


def read_meta(session_dir: Path) -> SessionMeta:
    return SessionMeta.model_validate_json(meta_path(session_dir).read_text())


def write_meta(session_dir: Path, meta: SessionMeta) -> None:
    meta_path(session_dir).write_text(meta.model_dump_json(indent=2))


def session_path(session_id: str) -> Path:
    return config.SESSIONS_DIR / session_id


def run_lock_path(session_dir: Path) -> Path:
    return session_dir / "run.lock"


def ensure_root_dirs() -> None:
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def validate_session_id(session_id: str) -> None:
    if not PROFILE_NAME_RE.fullmatch(session_id):
        raise SessionIdError(
            "invalid session id: use only letters, digits, '_', '-', and '.'"
        )
    if session_id in (".", ".."):
        raise SessionIdError("invalid session id: must not be '.' or '..'")


def allocate_session_id() -> str:
    """Allocate a fresh session id (UNIX seconds, +1 on collision)."""
    ensure_root_dirs()
    candidate = int(time.time())
    while True:
        path = session_path(str(candidate))
        try:
            path.mkdir(parents=True)
            return str(candidate)
        except FileExistsError:
            candidate += 1


def allocate_named_session_id(session_id: str) -> str:
    """Allocate a caller-provided session id without retrying on collision."""
    validate_session_id(session_id)
    ensure_root_dirs()
    try:
        session_path(session_id).mkdir(parents=True)
    except FileExistsError as e:
        raise SessionIdError(f"session already exists: {session_id}") from e
    return session_id


def is_run_locked(session_dir: Path) -> bool:
    return lock.flock_is_locked(run_lock_path(session_dir))


def resolve_session_dir(session_id: str) -> Path:
    try:
        validate_session_id(session_id)
    except SessionIdError as e:
        raise SystemExit(str(e)) from e
    path = session_path(session_id)
    if not path.exists():
        raise SystemExit(f"session not found: {session_id}")
    return path


def status_for_guards(session_dir: Path, meta: SessionMeta) -> SessionStatus:
    if is_run_locked(session_dir):
        return SessionStatus.running
    return meta.status


def is_runnable(status: SessionStatus) -> bool:
    return status in (
        SessionStatus.created,
        SessionStatus.done,
        SessionStatus.failed,
        SessionStatus.committed,
    )


def is_committable(status: SessionStatus) -> bool:
    return status in (
        SessionStatus.done,
        SessionStatus.failed,
        SessionStatus.committed,
    )


def is_running(status: SessionStatus) -> bool:
    return status == SessionStatus.running


def is_done(status: SessionStatus) -> bool:
    return status == SessionStatus.done


def create_session(
    a_arg: str,
    b_arg: str,
    *,
    profile_name: str = "default",
    session_id: str | None = None,
) -> str:
    a = Path(a_arg).resolve()
    b = Path(b_arg).resolve()

    raw_profile = profile_mod.load_profile_for_create(profile_name)
    effective_profile = profile_mod.effective_profile(raw_profile)
    skeleton.resolve_skeleton(effective_profile.skeleton)
    validate.preflight(a, b)

    ensure_root_dirs()

    session_id = (
        allocate_session_id()
        if session_id is None
        else allocate_named_session_id(session_id)
    )
    session_dir = session_path(session_id)
    work_dir = session_dir / "data"
    work_dir.mkdir(parents=True, exist_ok=True)

    mirror.build_work_dir(work_dir, a, b)
    instruction.install_agent_instructions(
        work_dir, effective_profile.agent_instructions
    )

    helper.chown_paths(
        session_dir.parent,
        work_dir,
        effective_profile,
        uid=effective_profile.guard_uid,
        gid=effective_profile.guard_gid,
    )

    agent_home = session_dir / "home" / "agent"
    agent_home.mkdir(parents=True)
    skeleton.copy_skeleton(effective_profile.skeleton, agent_home)

    helper.chown_paths(
        session_dir.parent,
        [work_dir / "inbox", agent_home],
        effective_profile,
        uid=effective_profile.agent_uid,
        gid=effective_profile.agent_gid,
    )

    subprocess.run(
        ["bash", str(GIT_SNAPSHOT_SCRIPT), str(session_dir)],
        check=True,
    )

    meta = SessionMeta(
        session_id=session_id,
        status=SessionStatus.created,
        created_at=now(),
        a=a,
        b=b,
        session_dir=session_dir,
        profile_name=profile_name,
        profile=raw_profile,
    )
    write_meta(session_dir, meta)

    return session_id


def list_sessions() -> list[tuple[str, str, str, str]]:
    sessions = config.SESSIONS_DIR
    if not sessions.exists():
        return []

    rows = []
    for entry in sorted(sessions.iterdir()):
        try:
            meta = read_meta(entry)
            status = status_for_guards(entry, meta)
            rows.append((meta.session_id, status.value, str(meta.a), str(meta.b)))
        except Exception:
            rows.append((entry.name, "?", "-", "-"))
    return rows


def meta_for_display(session_dir: Path) -> SessionMeta:
    meta = read_meta(session_dir)
    meta.status = status_for_guards(session_dir, meta)
    return meta


def mark_run_started(session_dir: Path) -> datetime:
    started_at = now()
    meta = read_meta(session_dir)
    meta.status = SessionStatus.failed
    meta.started_at = started_at
    meta.ended_at = None
    meta.exit_reason = "interrupted"
    write_meta(session_dir, meta)
    return started_at


def finish_run(
    session_dir: Path, *, started_at: datetime, return_code: int
) -> SessionMeta:
    meta = read_meta(session_dir)
    meta.started_at = started_at
    meta.ended_at = now()
    done_flag = session_dir / "data" / "outbox" / ".done"
    if done_flag.exists():
        meta.status = SessionStatus.done
        meta.exit_reason = "normal"
    elif return_code in (124, 137):
        meta.status = SessionStatus.failed
        meta.exit_reason = "timeout"
    else:
        meta.status = SessionStatus.failed
        meta.exit_reason = f"exit={return_code}"
    write_meta(session_dir, meta)
    return meta


def mark_committed(session_dir: Path) -> SessionMeta:
    meta = read_meta(session_dir)
    meta.status = SessionStatus.committed
    write_meta(session_dir, meta)
    return meta
