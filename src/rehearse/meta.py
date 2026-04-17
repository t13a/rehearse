"""SessionMeta Pydantic model and meta.json read/write helpers."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from rehearse.workspace import SessionIdError, validate_session_id


class SessionStatus(str, Enum):
    created = "created"
    running = "running"
    done = "done"
    failed = "failed"
    committed = "committed"


class SessionMeta(BaseModel):
    session_id: str
    status: SessionStatus
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    a: Path
    b: Path
    workspace: Path
    profile_name: str
    profile: dict[str, Any]
    exit_reason: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_persisted_session_id(cls, value: str) -> str:
        try:
            validate_session_id(value)
        except SessionIdError as e:
            raise ValueError(str(e)) from e
        return value

    @field_validator("status")
    @classmethod
    def reject_persisted_running(cls, value: SessionStatus) -> SessionStatus:
        if value == SessionStatus.running:
            raise ValueError("status=running must not be persisted")
        return value


def meta_path(workspace: Path) -> Path:
    return workspace / "meta.json"


def read_meta(workspace: Path) -> SessionMeta:
    return SessionMeta.model_validate_json(meta_path(workspace).read_text())


def write_meta(workspace: Path, meta: SessionMeta) -> None:
    meta_path(workspace).write_text(meta.model_dump_json(indent=2))
