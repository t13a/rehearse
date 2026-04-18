"""Shared helpers for shell-script contract tests."""

from __future__ import annotations

import stat
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_executable(path: Path, content: str) -> Path:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path
