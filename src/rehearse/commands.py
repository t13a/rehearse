"""Subcommand implementations for the rehearse CLI."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rehearse import (
    config,
    commit,
    docker,
    mirror,
    profile as profile_mod,
    skeleton,
    validate,
    workspace,
)
from rehearse.meta import SessionMeta, SessionStatus, read_meta, write_meta


REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_SNAPSHOT_SCRIPT = REPO_ROOT / "scripts" / "git-snapshot.sh"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_session_dir(session_id: str) -> Path:
    try:
        workspace.validate_session_id(session_id)
    except workspace.SessionIdError as e:
        raise SystemExit(str(e)) from e
    path = workspace.session_path(session_id)
    if not path.exists():
        raise SystemExit(f"session not found: {session_id}")
    return path


def _status_for_guards(session_dir: Path, meta: SessionMeta) -> SessionStatus:
    if workspace.flock_is_locked(workspace.run_lock_path(session_dir)):
        return SessionStatus.running
    return meta.status


def _install_agent_instructions(data_dir: Path, source: Path) -> None:
    if not source.is_file():
        raise profile_mod.ProfileError(f"agent instructions not found: {source}")
    (data_dir / "AGENTS.md").write_text(source.read_text())
    (data_dir / "CLAUDE.md").symlink_to("AGENTS.md")


# ---- create ------------------------------------------------------------

def cmd_create(
    a_arg: str,
    b_arg: str,
    *,
    profile_name: str = "default",
    session_id: str | None = None,
) -> int:
    a = Path(a_arg).resolve()
    b = Path(b_arg).resolve()

    try:
        raw_profile = profile_mod.load_profile_for_create(profile_name)
        effective_profile = profile_mod.effective_profile(raw_profile)
        skeleton.resolve_skeleton(effective_profile.skeleton)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2

    try:
        validate.preflight(a, b)
    except validate.PreflightError as e:
        print(f"preflight failed: {e}", file=sys.stderr)
        return 2

    workspace.ensure_root_dirs()

    try:
        session_id = (
            workspace.allocate_session_id()
            if session_id is None
            else workspace.allocate_named_session_id(session_id)
        )
    except workspace.SessionIdError as e:
        print(f"session failed: {e}", file=sys.stderr)
        return 2
    session_dir = workspace.session_path(session_id)
    data_dir = session_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    mirror.build_workspace_data(data_dir, a, b)
    try:
        _install_agent_instructions(data_dir, effective_profile.agent_instructions)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2

    docker.chown_container(
        session_dir,
        data_dir,
        effective_profile,
        uid=effective_profile.guard_uid,
        gid=effective_profile.guard_gid,
    )

    agent_home = session_dir / "home" / "agent"
    agent_home.mkdir(parents=True)
    try:
        skeleton.copy_skeleton(effective_profile.skeleton, agent_home)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2

    docker.chown_container(
        session_dir,
        [data_dir / "inbox", agent_home],
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
        created_at=_now(),
        a=a,
        b=b,
        workspace=session_dir,
        profile_name=profile_name,
        profile=raw_profile,
    )
    write_meta(session_dir, meta)

    print(session_id)
    return 0


# ---- status ------------------------------------------------------------

def cmd_status(session_id: str | None) -> int:
    if session_id is None:
        sessions = config.SESSIONS_DIR
        if not sessions.exists():
            return 0
        rows = []
        for entry in sorted(sessions.iterdir()):
            try:
                meta = read_meta(entry)
                status = _status_for_guards(entry, meta)
                rows.append((meta.session_id, status.value, str(meta.a), str(meta.b)))
            except Exception:
                rows.append((entry.name, "?", "-", "-"))
        for sid, status, a, b in rows:
            print(f"{sid}\t{status}\t{a}\t{b}")
        return 0

    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)
    meta.status = _status_for_guards(session_dir, meta)
    print(meta.model_dump_json(indent=2))
    return 0


# ---- run / debug -------------------------------------------------------

def cmd_run(session_id: str, *, message: str | None = None) -> int:
    return _cmd_run_like(session_id, message=message, debug_argv=None)


def cmd_debug(session_id: str, argv: list[str]) -> int:
    if not argv:
        print("usage: rehearse debug <session> CMD [ARGS...]", file=sys.stderr)
        return 2
    return _cmd_run_like(session_id, message=None, debug_argv=argv)


def _cmd_run_like(
    session_id: str,
    *,
    message: str | None,
    debug_argv: list[str] | None,
) -> int:
    verb = "debug" if debug_argv is not None else "run"
    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)
    try:
        effective_profile = profile_mod.effective_profile(meta.profile)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2

    status = _status_for_guards(session_dir, meta)
    allowed = (
        SessionStatus.created,
        SessionStatus.done,
        SessionStatus.failed,
        SessionStatus.committed,
    )
    if status not in allowed:
        print(
            f"cannot {verb} session in status={status.value}",
            file=sys.stderr,
        )
        return 2

    started_at = _now()
    meta.status = SessionStatus.failed
    meta.started_at = started_at
    meta.ended_at = None
    meta.exit_reason = "interrupted"
    write_meta(session_dir, meta)

    if debug_argv is None:
        rc = docker.run_agent(
            session_dir, meta.a, meta.b, effective_profile, message=message
        )
    else:
        rc = docker.run_debug(session_dir, meta.a, meta.b, effective_profile, debug_argv)
    if rc == docker.RUN_LOCK_BUSY_EXIT:
        print(f"cannot {verb} a running session", file=sys.stderr)
        return 2

    meta = read_meta(session_dir)
    meta.started_at = started_at
    meta.ended_at = _now()
    done_flag = session_dir / "data" / "outbox" / ".done"
    if done_flag.exists():
        meta.status = SessionStatus.done
        meta.exit_reason = "normal"
    elif rc in (124, 137):
        meta.status = SessionStatus.failed
        meta.exit_reason = "timeout"
    else:
        meta.status = SessionStatus.failed
        meta.exit_reason = f"exit={rc}"
    write_meta(session_dir, meta)
    return 0 if meta.status == SessionStatus.done else 1


# ---- purge -------------------------------------------------------------

def cmd_purge(session_id: str) -> int:
    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)
    status = _status_for_guards(session_dir, meta)
    if status == SessionStatus.running:
        print("cannot purge a running session", file=sys.stderr)
        return 2
    try:
        effective_profile = profile_mod.effective_profile(meta.profile)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2
    docker.cleanup_container(session_dir, effective_profile)
    return 0


# ---- commit ------------------------------------------------------------

def cmd_commit(session_id: str) -> int:
    session_dir = _resolve_session_dir(session_id)
    meta = read_meta(session_dir)

    status = _status_for_guards(session_dir, meta)
    allowed = (SessionStatus.done, SessionStatus.failed, SessionStatus.committed)
    if status not in allowed:
        print(
            f"cannot commit session in status={status.value}",
            file=sys.stderr,
        )
        return 2

    with workspace.flock_exclusive(workspace.b_lock_path(meta.b)):
        try:
            stats = commit.commit_session(session_dir, meta.a, meta.b)
        except commit.CommitAbort as e:
            print(f"commit aborted: {e}", file=sys.stderr)
            return 1

    meta.status = SessionStatus.committed
    write_meta(session_dir, meta)
    print(
        f"committed: moved={stats.moved} already_moved={stats.already_moved} "
        f"skipped_b={stats.skipped_b} skipped_file={stats.skipped_file} "
        f"inbox_remaining={stats.inbox_remaining} a_remaining={stats.a_remaining}"
    )
    if stats.inbox_remaining > 0:
        print(
            f"warning: {stats.inbox_remaining} file(s) in inbox/ were not moved to outbox/",
            file=sys.stderr,
        )
    elif stats.a_remaining > 0:
        print(
            f"warning: inbox/ is empty but {stats.a_remaining} file(s) remain in A — "
            f"create a new session to process them",
            file=sys.stderr,
        )
    return 0


# ---- exec --------------------------------------------------------------

def cmd_exec(session_id: str, argv: list[str]) -> int:
    if not argv:
        print("usage: rehearse exec <session> CMD [ARGS...]", file=sys.stderr)
        return 2
    session_dir = _resolve_session_dir(session_id)
    data_dir = session_dir / "data"
    return subprocess.run(argv, cwd=data_dir).returncode
