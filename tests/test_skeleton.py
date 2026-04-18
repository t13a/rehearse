"""Tests for home skeleton resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from rehearse import config, skeleton
from rehearse.profile import ProfileError


def test_resolve_skeleton_ensures_directory_if_name_is_default(
    rehearse_root: Path,
) -> None:
    default = config.SKELETONS_DIR / "default"
    assert not default.exists()

    resolved = skeleton.resolve_skeleton("default")

    assert resolved == default
    assert default.is_dir()


def test_resolve_skeleton_rejects_missing_name(
    rehearse_root: Path,
) -> None:
    with pytest.raises(ProfileError, match="skeleton not found: ghost"):
        skeleton.resolve_skeleton("ghost")


def test_copy_skeleton_preserves_files_symlinks_and_independence(
    rehearse_root: Path,
    tmp_path: Path,
) -> None:
    src = config.SKELETONS_DIR / "codex"
    (src / ".codex").mkdir(parents=True)
    (src / ".codex" / "auth.json").write_text('{"token": "secret"}\n')
    (src / ".codex" / "config.toml").write_text("model = 'gpt-5.4'\n")
    (src / "auth-link").symlink_to(".codex/auth.json")

    dest = tmp_path / "agent-home"

    skeleton.copy_skeleton("codex", dest)

    assert (dest / ".codex" / "auth.json").read_text() == '{"token": "secret"}\n'
    assert (dest / ".codex" / "config.toml").read_text() == "model = 'gpt-5.4'\n"
    assert (dest / "auth-link").is_symlink()
    assert (dest / "auth-link").readlink() == Path(".codex/auth.json")

    (src / ".codex" / "auth.json").write_text('{"token": "changed-source"}\n')
    assert (dest / ".codex" / "auth.json").read_text() == '{"token": "secret"}\n'

    (dest / ".codex" / "auth.json").write_text('{"token": "changed-dest"}\n')
    assert (src / ".codex" / "auth.json").read_text() == '{"token": "changed-source"}\n'
