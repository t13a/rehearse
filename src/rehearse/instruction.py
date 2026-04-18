"""Agent instruction installation for working directory."""

from __future__ import annotations

from pathlib import Path


class InstructionError(RuntimeError):
    """Raised when agent instructions cannot be installed."""


def install_agent_instructions(work_dir: Path, source: Path) -> None:
    if not source.is_file():
        raise InstructionError(f"agent instructions not found: {source}")
    (work_dir / "AGENTS.md").write_text(source.read_text())
    (work_dir / "CLAUDE.md").symlink_to("AGENTS.md")
