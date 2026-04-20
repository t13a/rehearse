"""Tests for installing agent instructions into a session work tree."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rehearse import instruction


def test_install_agent_instructions_copies_agents_and_claude_alias(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    source = tmp_path / "default.md"
    source.write_text("# Instructions\n")

    instruction.install_agent_instructions(work_dir, source)

    assert (work_dir / "AGENTS.md").read_text() == "# Instructions\n"
    assert (work_dir / "CLAUDE.md").is_symlink()
    assert os.readlink(work_dir / "CLAUDE.md") == "AGENTS.md"

    source.write_text("# Changed\n")
    assert (work_dir / "AGENTS.md").read_text() == "# Instructions\n"


def test_install_agent_instructions_rejects_missing_source(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    with pytest.raises(instruction.InstructionError, match="agent instructions not found"):
        instruction.install_agent_instructions(work_dir, tmp_path / "missing.md")
