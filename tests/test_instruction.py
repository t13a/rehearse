"""Tests for installing agent instructions into a session data tree."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rehearse import instruction


def test_install_agent_instructions_copies_agents_and_claude_alias(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    source = tmp_path / "default.md"
    source.write_text("# Instructions\n")

    instruction.install_agent_instructions(data, source)

    assert (data / "AGENTS.md").read_text() == "# Instructions\n"
    assert (data / "CLAUDE.md").is_symlink()
    assert os.readlink(data / "CLAUDE.md") == "AGENTS.md"

    source.write_text("# Changed\n")
    assert (data / "AGENTS.md").read_text() == "# Instructions\n"


def test_install_agent_instructions_rejects_missing_source(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()

    with pytest.raises(instruction.InstructionError, match="agent instructions not found"):
        instruction.install_agent_instructions(data, tmp_path / "missing.md")
