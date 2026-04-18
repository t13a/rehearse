"""Build the session `data/` tree: refs/{a,b} symlinks + inbox/ and outbox/ mirrors."""

from __future__ import annotations

import os
from pathlib import Path


C_MODE = 0o777
D_MODE = 0o1777  # sticky


def _chmod_tree(root: Path, mode: int) -> None:
    """Force-set mode on `root` and all descendant directories.

    Python's mkdir honors umask, so set the exact mode ourselves.
    """
    os.chmod(root, mode)
    for dirpath, dirnames, _ in os.walk(root):
        for d in dirnames:
            os.chmod(Path(dirpath) / d, mode)


def _mirror(
    source: Path, dest_root: Path, link_into: Path, dir_mode: int
) -> None:
    """Walk `source`, create parents under `dest_root`, symlink files to `link_into`.

    Every file under `source` becomes a symlink at the corresponding relative
    path in `dest_root`, with an absolute target under `link_into`.
    """
    dest_root.mkdir(parents=True, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        rel = Path(dirpath).relative_to(source)
        dest_dir = dest_root / rel
        dest_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            link = dest_dir / name
            target = link_into / rel / name
            link.symlink_to(target)
    _chmod_tree(dest_root, dir_mode)


def build_work_dir(
    work_dir: Path, a: Path, b: Path
) -> None:
    """Construct `data/` contents: refs/{a,b} symlinks + inbox/ + outbox/ mirrors.

    Assumes `work_dir` already exists and is empty.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    refs_dir = work_dir / "refs"
    refs_dir.mkdir()
    (refs_dir / "a").symlink_to(a)
    (refs_dir / "b").symlink_to(b)

    ref_a = refs_dir / "a"
    ref_b = refs_dir / "b"

    _mirror(a, work_dir / "inbox", ref_a, C_MODE)
    _mirror(b, work_dir / "outbox", ref_b, D_MODE)
