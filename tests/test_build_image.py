"""CLI tests for building bundled agent images."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rehearse import cli, resource


def test_build_image_uses_bundled_script_without_custom_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_path(*parts: str) -> Path:
        return tmp_path.joinpath(*parts)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(resource, "path", fake_path)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli.main(["build-image", "codex"]) == 0
    assert calls == [["bash", str(tmp_path / "scripts" / "build-agent-codex-image.sh")]]


def test_build_image_passes_custom_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_path(*parts: str) -> Path:
        return tmp_path.joinpath(*parts)

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(resource, "path", fake_path)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli.main(["build-image", "claude", "rehearse-agent-claude:test"]) == 7
    assert calls == [
        [
            "bash",
            str(tmp_path / "scripts" / "build-agent-claude-image.sh"),
            "rehearse-agent-claude:test",
        ]
    ]
