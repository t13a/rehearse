"""Environment-driven configuration for rehearse."""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


REHEARSE_ROOT: Path = _env_path(
    "REHEARSE_ROOT", Path.home() / ".local" / "share" / "rehearse"
)

REHEARSE_AGENT_UID: int = _env_int("REHEARSE_AGENT_UID", 10000)
REHEARSE_AGENT_GID: int = _env_int("REHEARSE_AGENT_GID", 10000)

REHEARSE_AGENT_IMAGE: str = _env_str("REHEARSE_AGENT_IMAGE", "rehearse-agent:latest")
REHEARSE_HELPER_IMAGE: str = _env_str("REHEARSE_HELPER_IMAGE", "busybox:latest")

REHEARSE_AGENT_TIMEOUT: int = _env_int("REHEARSE_AGENT_TIMEOUT", 3600)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RUNNER = _REPO_ROOT / "scripts" / "run-agent-cc.sh"
REHEARSE_AGENT_RUNNER: Path = _env_path("REHEARSE_AGENT_RUNNER", _DEFAULT_RUNNER)

_mcp = os.environ.get("REHEARSE_MCP_CONFIG")
REHEARSE_MCP_CONFIG: Path | None = (
    Path(_mcp).expanduser().resolve() if _mcp else None
)

SESSIONS_DIR: Path = REHEARSE_ROOT / "sessions"
LOCKS_DIR: Path = REHEARSE_ROOT / "locks"


def reload() -> None:
    """Re-read environment variables into module attributes.

    Tests that monkeypatch REHEARSE_* after import call this to refresh.
    """
    global REHEARSE_ROOT, REHEARSE_AGENT_UID, REHEARSE_AGENT_GID
    global REHEARSE_AGENT_IMAGE, REHEARSE_HELPER_IMAGE
    global REHEARSE_AGENT_TIMEOUT, REHEARSE_AGENT_RUNNER, REHEARSE_MCP_CONFIG
    global SESSIONS_DIR, LOCKS_DIR

    REHEARSE_ROOT = _env_path(
        "REHEARSE_ROOT", Path.home() / ".local" / "share" / "rehearse"
    )
    REHEARSE_AGENT_UID = _env_int("REHEARSE_AGENT_UID", 10000)
    REHEARSE_AGENT_GID = _env_int("REHEARSE_AGENT_GID", 10000)
    REHEARSE_AGENT_IMAGE = _env_str("REHEARSE_AGENT_IMAGE", "rehearse-agent:latest")
    REHEARSE_HELPER_IMAGE = _env_str("REHEARSE_HELPER_IMAGE", "busybox:latest")
    REHEARSE_AGENT_TIMEOUT = _env_int("REHEARSE_AGENT_TIMEOUT", 3600)
    REHEARSE_AGENT_RUNNER = _env_path("REHEARSE_AGENT_RUNNER", _DEFAULT_RUNNER)
    _mcp_reload = os.environ.get("REHEARSE_MCP_CONFIG")
    REHEARSE_MCP_CONFIG = (
        Path(_mcp_reload).expanduser().resolve() if _mcp_reload else None
    )
    SESSIONS_DIR = REHEARSE_ROOT / "sessions"
    LOCKS_DIR = REHEARSE_ROOT / "locks"
