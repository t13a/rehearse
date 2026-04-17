"""Session workspace path resolution and id allocation."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from rehearse import config
from rehearse.profile import PROFILE_NAME_RE


class SessionIdError(RuntimeError):
    """Raised when a requested session id is invalid or unavailable."""


def sessions_dir() -> Path:
    return config.SESSIONS_DIR


def locks_dir() -> Path:
    return config.LOCKS_DIR


def session_path(session_id: str) -> Path:
    return sessions_dir() / session_id


def data_path(session_id: str) -> Path:
    return session_path(session_id) / "data"


def run_lock_path(session_dir: Path) -> Path:
    return session_dir / "run.lock"


def ensure_root_dirs() -> None:
    sessions_dir().mkdir(parents=True, exist_ok=True)
    locks_dir().mkdir(parents=True, exist_ok=True)


def validate_session_id(session_id: str) -> None:
    if not PROFILE_NAME_RE.fullmatch(session_id):
        raise SessionIdError(
            "invalid session id: use only letters, digits, '_', '-', and '.'"
        )
    if session_id in (".", ".."):
        raise SessionIdError("invalid session id: must not be '.' or '..'")


@contextmanager
def flock_exclusive(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = lock_path.open("w")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        fd.close()


def flock_is_locked(lock_path: Path) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = lock_path.open("a")
    try:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                return True
            raise
        else:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            return False
    finally:
        fd.close()


def b_lock_path(b: Path) -> Path:
    """Path to the advisory lock file for a given B directory.

    Used by `commit` to serialize concurrent commits against the same B.
    The lock file itself is created on first use and intentionally left on
    disk afterwards — flock is inode-scoped, so unlinking it races with
    other processes' open() calls. One tiny file per unique B is fine.
    """
    digest = hashlib.sha256(str(b).encode()).hexdigest()[:16]
    return locks_dir() / f"b-{digest}.lock"


def allocate_session_id() -> str:
    """Allocate a fresh session id (UNIX seconds, +1 on collision).

    Relies on `mkdir(2)` being atomic: two racing callers cannot both create
    the same directory, so the loser just increments and retries.
    """
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
