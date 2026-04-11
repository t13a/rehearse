"""Session workspace path resolution and id allocation."""

from __future__ import annotations

import fcntl
import hashlib
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from rehearse import config


def sessions_dir() -> Path:
    return config.SESSIONS_DIR


def locks_dir() -> Path:
    return config.LOCKS_DIR


def session_path(session_id: str) -> Path:
    return sessions_dir() / session_id


def data_path(session_id: str) -> Path:
    return session_path(session_id) / "data"


def ensure_root_dirs() -> None:
    sessions_dir().mkdir(parents=True, exist_ok=True)
    locks_dir().mkdir(parents=True, exist_ok=True)


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


def b_lock_path(b: Path) -> Path:
    digest = hashlib.sha256(str(b).encode()).hexdigest()[:16]
    return locks_dir() / f"b-{digest}.lock"


def _alloc_lock_path() -> Path:
    return locks_dir() / "alloc.lock"


def allocate_session_id() -> str:
    """Allocate a fresh session id (UNIX seconds, +1 on collision).

    Holds an advisory lock so concurrent `create` invocations don't collide.
    """
    ensure_root_dirs()
    with flock_exclusive(_alloc_lock_path()):
        candidate = int(time.time())
        while session_path(str(candidate)).exists():
            candidate += 1
        session_path(str(candidate)).mkdir(parents=True)
        return str(candidate)
