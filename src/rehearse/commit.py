"""Idempotent commit algorithm: rename real files from A to B based on d/ symlinks."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO


class CommitAbort(RuntimeError):
    """Raised when the commit encounters an unrecoverable state."""


@dataclass
class CommitStats:
    moved: int = 0
    already_moved: int = 0
    skipped_b: int = 0
    skipped_file: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(fh: IO[str], **fields: object) -> None:
    entry = {"ts": _now_iso(), **fields}
    fh.write(json.dumps(entry, default=str) + "\n")
    fh.flush()


def commit_session(session_dir: Path, a: Path, b: Path) -> CommitStats:
    data = session_dir / "data"
    d = data / "d"
    a_prefix = str(data / "a") + "/"
    b_prefix = str(data / "b") + "/"

    stats = CommitStats()
    log_path = session_dir / "commit.log"

    with log_path.open("a") as fh:
        for dirpath, _dirnames, filenames in os.walk(d, followlinks=False):
            for name in filenames:
                entry = Path(dirpath) / name
                if not entry.is_symlink():
                    stats.skipped_file += 1
                    continue
                _handle_symlink(entry, d, a, b, a_prefix, b_prefix, stats, fh)

        _log(fh, op="done", **asdict(stats))

    return stats


def _handle_symlink(
    link: Path,
    d: Path,
    a: Path,
    b: Path,
    a_prefix: str,
    b_prefix: str,
    stats: CommitStats,
    fh: IO[str],
) -> None:
    target = os.readlink(link)
    rel = link.relative_to(d)
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
