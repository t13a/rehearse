"""Idempotent commit algorithm: rename real files from A to B based on outbox/ symlinks."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO

from rehearse import config, lock


class CommitAbort(RuntimeError):
    """Raised when the commit encounters an unrecoverable state."""


@dataclass
class CommitStats:
    moved: int = 0
    already_moved: int = 0
    skipped_b: int = 0
    skipped_file: int = 0
    inbox_remaining: int = 0
    a_remaining: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(fh: IO[str], **fields: object) -> None:
    entry = {"ts": _now_iso(), **fields}
    fh.write(json.dumps(entry, default=str) + "\n")
    fh.flush()


def b_lock_path(b: Path) -> Path:
    """Path to the advisory lock file for a given B directory."""
    digest = hashlib.sha256(str(b).encode()).hexdigest()[:16]
    return config.LOCKS_DIR / f"b-{digest}.lock"


def commit_session_with_lock(session_dir: Path, a: Path, b: Path) -> CommitStats:
    with lock.flock_exclusive(b_lock_path(b)):
        return commit_session(session_dir, a, b)


def commit_session(session_dir: Path, a: Path, b: Path) -> CommitStats:
    data = session_dir / "data"
    outbox = data / "outbox"
    a_prefix = str(data / "refs" / "a") + "/"
    b_prefix = str(data / "refs" / "b") + "/"

    stats = CommitStats()
    log_path = session_dir / "commit.log"

    with log_path.open("a") as fh:
        for dirpath, _dirnames, filenames in os.walk(outbox, followlinks=False):
            for name in filenames:
                entry = Path(dirpath) / name
                if not entry.is_symlink():
                    stats.skipped_file += 1
                    continue
                _handle_symlink(entry, outbox, a, b, a_prefix, b_prefix, stats, fh)

        inbox = data / "inbox"
        for dirpath, _dn, fnames in os.walk(inbox, followlinks=False):
            for name in fnames:
                entry = Path(dirpath) / name
                if entry.is_symlink() and Path(os.readlink(entry)).exists():
                    stats.inbox_remaining += 1

        for dirpath, _dn, fnames in os.walk(a, followlinks=False):
            for name in fnames:
                stats.a_remaining += 1

        _log(fh, op="done", **asdict(stats))

    return stats


def _handle_symlink(
    link: Path,
    outbox: Path,
    a: Path,
    b: Path,
    a_prefix: str,
    b_prefix: str,
    stats: CommitStats,
    fh: IO[str],
) -> None:
    target = os.readlink(link)
    rel = link.relative_to(outbox)
    dst = b / rel

    if target.startswith(b_prefix):
        stats.skipped_b += 1
        return

    if not target.startswith(a_prefix):
        _log(fh, op="unexpected-target", target=target)
        raise CommitAbort(f"unexpected symlink target: {target}")

    suffix = target[len(a_prefix):]
    src = a / suffix

    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        stats.moved += 1
        _log(fh, op="moved", src=str(src), dst=str(dst))

    elif not src.exists() and dst.exists():
        stats.already_moved += 1
        _log(fh, op="already-moved", src=str(src), dst=str(dst))

    elif src.exists() and dst.exists():
        _log(fh, op="conflict", src=str(src), dst=str(dst))
        raise CommitAbort(f"both src and dst exist: {src} / {dst}")

    else:
        _log(fh, op="missing", src=str(src), dst=str(dst))
        raise CommitAbort(f"neither src nor dst exists: {src} / {dst}")
