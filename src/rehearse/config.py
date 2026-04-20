"""Global configuration for rehearse."""

from __future__ import annotations

import os
from pathlib import Path

from rehearse import resource


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


REHEARSE_ROOT: Path = _env_path(
    "REHEARSE_ROOT", Path.home() / ".local" / "share" / "rehearse"
)

DEFAULT_AGENT: str = "codex"
DEFAULT_AGENT_UID: int = os.getuid()
DEFAULT_AGENT_GID: int = os.getgid()
DEFAULT_GUARD_UID: int = 65534
DEFAULT_GUARD_GID: int = 65534
DEFAULT_CODEX_AGENT_IMAGE: str = "rehearse-agent-codex:latest"
DEFAULT_CLAUDE_AGENT_IMAGE: str = "rehearse-agent-claude:latest"
DEFAULT_HELPER_IMAGE: str = "busybox:latest"
DEFAULT_AGENT_TIMEOUT: int = 3600
DEFAULT_AGENT_INSTRUCTIONS: Path = resource.path("instructions", "default.md")
DEFAULT_AGENT_RUNNER: Path = resource.path("scripts", "docker-runner.sh")
DEFAULT_DOCKER_HELPER: Path = resource.path("scripts", "docker-helper.sh")

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
