"""Tests for installing agent instructions into a session work tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from rehearse import instruction


def test_install_agent_instructions_copies_agents_only(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    source = tmp_path / "default.md"
    source.write_text("# Instructions\n")

    instruction.install_agent_instructions(work_dir, source)

    assert (work_dir / "AGENTS.md").read_text() == "# Instructions\n"
    assert [p.name for p in work_dir.iterdir()] == ["AGENTS.md"]

    source.write_text("# Changed\n")
    assert (work_dir / "AGENTS.md").read_text() == "# Instructions\n"


def test_install_agent_instructions_rejects_missing_source(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    with pytest.raises(instruction.InstructionError, match="agent instructions not found"):
        instruction.install_agent_instructions(work_dir, tmp_path / "missing.md")
