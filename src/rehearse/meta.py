"""SessionMeta Pydantic model and meta.json read/write helpers."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class SessionStatus(str, Enum):
    created = "created"
    running = "running"
    done = "done"
    failed = "failed"
    committed = "committed"
    discarded = "discarded"


class SessionMeta(BaseModel):
    session_id: str
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    a: Path
    b: Path
    workspace: Path
    agent_image: str
    agent_uid: int
    agent_gid: int
    exit_reason: str | None = None


def meta_path(workspace: Path) -> Path:
    return workspace / "meta.json"


def read_meta(workspace: Path) -> SessionMeta:
    return SessionMeta.model_validate_json(meta_path(workspace).read_text())


def write_meta(workspace: Path, meta: SessionMeta) -> None:
    meta_path(workspace).write_text(meta.model_dump_json(indent=2))
