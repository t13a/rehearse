"""argparse entry point for the `rehearse` command."""

from __future__ import annotations

import argparse
from typing import Sequence

from rehearse import commands


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

    p_status = sub.add_parser("status", help="list sessions or show one")
    p_status.add_argument("session_id", nargs="?", default=None)

    p_run = sub.add_parser("run", help="run the agent for a session")
    p_run.add_argument("session_id")
    p_run.add_argument("-m", "--message", default=None,
                       help="message to pass to the agent")

    p_purge = sub.add_parser("purge", help="delete a session workspace")
    p_purge.add_argument("session_id")

    p_commit = sub.add_parser("commit", help="commit a session's plan")
    p_commit.add_argument("session_id")

    p_exec = sub.add_parser("exec", help="run a command in the session data directory")
    p_exec.add_argument("session_id")
    p_exec.add_argument("argv", nargs=argparse.REMAINDER)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    match args.command:
        case "create":
            return commands.cmd_create(
                args.a,
                args.b,
                profile_name=args.profile,
                session_id=args.session,
            )
        case "status":
            return commands.cmd_status(args.session_id)
        case "run":
            return commands.cmd_run(args.session_id, message=args.message)
        case "purge":
            return commands.cmd_purge(args.session_id)
        case "commit":
            return commands.cmd_commit(args.session_id)
        case "exec":
            return commands.cmd_exec(args.session_id, args.argv)
        case _:
            parser.error(f"unknown command: {args.command}")
            return 2
