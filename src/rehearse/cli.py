"""argparse entry point and command controller for `rehearse`."""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Sequence

from rehearse import (
    commit,
    helper,
    instruction,
    profile as profile_mod,
    run,
    session,
    validate,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rehearse",
        description="symlink-staging harness for AI-driven large-file organization",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="create a new session")
    p_create.add_argument("-p", "--profile", default="default",
                          help="profile name (default: default)")
    p_create.add_argument("-s", "--session", default=None,
                          help="session id to create")
    p_create.add_argument("a", help="source directory A")
    p_create.add_argument("b", help="target library B")
    p_create.set_defaults(func=_cmd_create)

    p_status = sub.add_parser("status", help="list sessions or show one")
    p_status.add_argument("session_id", nargs="?", default=None)
    p_status.set_defaults(func=_cmd_status)

    p_run = sub.add_parser("run", help="run the agent for a session")
    p_run.add_argument("session_id")
    p_run.add_argument("-m", "--message", default=None,
                       help="message to pass to the agent")
    p_run.set_defaults(func=_cmd_run)

    p_debug = sub.add_parser("debug", help="run a command in the agent image")
    p_debug.add_argument("session_id")
    p_debug.add_argument("argv", nargs=argparse.REMAINDER)
    p_debug.set_defaults(func=_cmd_debug)

    p_delete = sub.add_parser("delete", help="delete a session")
    p_delete.add_argument("session_id")
    p_delete.set_defaults(func=_cmd_delete)

    p_commit = sub.add_parser("commit", help="commit a session's plan")
    p_commit.add_argument("session_id")
    p_commit.set_defaults(func=_cmd_commit)

    p_exec = sub.add_parser("exec", help="run a command in the agent work directory")
    p_exec.add_argument("session_id")
    p_exec.add_argument("argv", nargs=argparse.REMAINDER)
    p_exec.set_defaults(func=_cmd_exec)

    return parser


def _cmd_create(args: argparse.Namespace) -> int:
    try:
        session_id = session.create_session(
            args.a,
            args.b,
            profile_name=args.profile,
            session_id=args.session,
        )
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2
    except instruction.InstructionError as e:
        print(f"instruction failed: {e}", file=sys.stderr)
        return 2
    except validate.PreflightError as e:
        print(f"preflight failed: {e}", file=sys.stderr)
        return 2
    except session.SessionIdError as e:
        print(f"session failed: {e}", file=sys.stderr)
        return 2

    print(session_id)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    if args.session_id is None:
        for sid, status, a, b in session.list_sessions():
            print(f"{sid}\t{status}\t{a}\t{b}")
        return 0

    session_dir = session.resolve_session_dir(args.session_id)
    meta = session.meta_for_display(session_dir)
    print(meta.model_dump_json(indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    return _cmd_run_like(args.session_id, message=args.message, debug_argv=None)


def _cmd_debug(args: argparse.Namespace) -> int:
    if not args.argv:
        print("usage: rehearse debug <session> CMD [ARGS...]", file=sys.stderr)
        return 2
    return _cmd_run_like(args.session_id, message=None, debug_argv=args.argv)


def _cmd_run_like(
    session_id: str,
    *,
    message: str | None,
    debug_argv: list[str] | None,
) -> int:
    verb = "debug" if debug_argv is not None else "run"
    session_dir = session.resolve_session_dir(session_id)
    meta = session.read_meta(session_dir)
    try:
        effective_profile = profile_mod.effective_profile(meta.profile)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2

    status = session.status_for_guards(session_dir, meta)
    if not session.is_runnable(status):
        print(
            f"cannot {verb} session in status={status.value}",
            file=sys.stderr,
        )
        return 2

    started_at = session.mark_run_started(session_dir)

    if debug_argv is None:
        rc = run.run_agent(
            session_dir,
            meta.a,
            meta.b,
            effective_profile,
            run_lock_path=session.run_lock_path(session_dir),
            message=message,
        )
    else:
        rc = run.run_debug(
            session_dir,
            meta.a,
            meta.b,
            effective_profile,
            run_lock_path=session.run_lock_path(session_dir),
            argv=debug_argv,
        )
    if rc == run.RUN_LOCK_BUSY_EXIT:
        print(f"cannot {verb} a running session", file=sys.stderr)
        return 2

    meta = session.finish_run(session_dir, started_at=started_at, return_code=rc)
    return 0 if session.is_done(meta.status) else 1


def _cmd_delete(args: argparse.Namespace) -> int:
    session_dir = session.resolve_session_dir(args.session_id)
    meta = session.read_meta(session_dir)
    status = session.status_for_guards(session_dir, meta)
    if session.is_running(status):
        print("cannot delete a running session", file=sys.stderr)
        return 2
    try:
        effective_profile = profile_mod.effective_profile(meta.profile)
    except profile_mod.ProfileError as e:
        print(f"profile failed: {e}", file=sys.stderr)
        return 2
    helper.remove_tree(session_dir.parent, session_dir, effective_profile)
    return 0


def _cmd_commit(args: argparse.Namespace) -> int:
    session_dir = session.resolve_session_dir(args.session_id)
    meta = session.read_meta(session_dir)

    status = session.status_for_guards(session_dir, meta)
    if not session.is_committable(status):
        print(
            f"cannot commit session in status={status.value}",
            file=sys.stderr,
        )
        return 2

    try:
        stats = commit.commit_session_with_lock(session_dir, meta.a, meta.b)
    except commit.CommitAbort as e:
        print(f"commit aborted: {e}", file=sys.stderr)
        return 1

    session.mark_committed(session_dir)
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


def _cmd_exec(args: argparse.Namespace) -> int:
    if not args.argv:
        print("usage: rehearse exec <session> CMD [ARGS...]", file=sys.stderr)
        return 2
    session_dir = session.resolve_session_dir(args.session_id)
    work_dir = session_dir / "work"
    return subprocess.run(args.argv, cwd=work_dir).returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
