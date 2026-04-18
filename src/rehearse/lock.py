"""Low-level advisory file locks."""

from __future__ import annotations

import errno
import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


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
