"""Tests for bundled resource path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

from rehearse import resource


def test_source_resource_paths_exist() -> None:
    assert resource.path("instructions", "default.md").is_file()
    assert resource.path("scripts", "docker-runner.sh").is_file()
    assert resource.path("scripts", "docker-helper.sh").is_file()
    assert resource.path("scripts", "git-snapshot.sh").is_file()
    assert resource.path("docker", "codex", "Dockerfile").is_file()
    assert resource.path("docker", "claude", "Dockerfile").is_file()


def test_resource_root_uses_pyinstaller_bundle_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert resource.root() == tmp_path
    assert resource.path("scripts", "docker-runner.sh") == (
        tmp_path / "scripts" / "docker-runner.sh"
    )
