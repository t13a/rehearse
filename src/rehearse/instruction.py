"""Agent instruction installation for session workspaces."""

from __future__ import annotations

from pathlib import Path


class InstructionError(RuntimeError):
    """Raised when agent instructions cannot be installed."""


def install_agent_instructions(data_dir: Path, source: Path) -> None:
    if not source.is_file():
        raise InstructionError(f"agent instructions not found: {source}")
    (data_dir / "AGENTS.md").write_text(source.read_text())
    (data_dir / "CLAUDE.md").symlink_to("AGENTS.md")
