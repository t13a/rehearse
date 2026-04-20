"""Locate files bundled with the rehearse executable."""

from __future__ import annotations

import sys
from pathlib import Path


def root() -> Path:
    """Return the directory containing bundled rehearse resources."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


def path(*parts: str) -> Path:
    """Return a path below the bundled resource root."""

    return root().joinpath(*parts)
