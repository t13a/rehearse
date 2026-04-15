"""Global configuration for rehearse."""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


REHEARSE_ROOT: Path = _env_path(
    "REHEARSE_ROOT", Path.home() / ".local" / "share" / "rehearse"
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT: str = "codex"
DEFAULT_AGENT_UID: int = 10000
DEFAULT_AGENT_GID: int = 10000
DEFAULT_CODEX_AGENT_IMAGE: str = "rehearse-agent-codex:latest"
DEFAULT_CLAUDE_CODE_AGENT_IMAGE: str = "rehearse-agent-cc:latest"
DEFAULT_AGENT_IMAGE: str = DEFAULT_CODEX_AGENT_IMAGE
DEFAULT_HELPER_IMAGE: str = "busybox:latest"
DEFAULT_AGENT_TIMEOUT: int = 3600
DEFAULT_CODEX_AGENT_RUNNER: Path = _REPO_ROOT / "scripts" / "run-agent-codex.sh"
DEFAULT_CLAUDE_CODE_AGENT_RUNNER: Path = _REPO_ROOT / "scripts" / "run-agent-cc.sh"
DEFAULT_AGENT_RUNNER: Path = DEFAULT_CODEX_AGENT_RUNNER

SESSIONS_DIR: Path = REHEARSE_ROOT / "sessions"
LOCKS_DIR: Path = REHEARSE_ROOT / "locks"
PROFILES_DIR: Path = REHEARSE_ROOT / "profiles"
SKELETONS_DIR: Path = REHEARSE_ROOT / "skeletons"


def reload() -> None:
    """Re-read environment variables into module attributes."""

    global REHEARSE_ROOT, SESSIONS_DIR, LOCKS_DIR, PROFILES_DIR, SKELETONS_DIR

    REHEARSE_ROOT = _env_path(
        "REHEARSE_ROOT", Path.home() / ".local" / "share" / "rehearse"
    )
    SESSIONS_DIR = REHEARSE_ROOT / "sessions"
    LOCKS_DIR = REHEARSE_ROOT / "locks"
    PROFILES_DIR = REHEARSE_ROOT / "profiles"
    SKELETONS_DIR = REHEARSE_ROOT / "skeletons"
