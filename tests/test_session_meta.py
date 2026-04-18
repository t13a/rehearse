"""Tests for session meta validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rehearse.session import SessionMeta


def test_session_meta_rejects_persisted_running_status(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="status=running must not be persisted"):
        SessionMeta(
            session_id="123",
            status="running",
            created_at=datetime.now(timezone.utc),
            a=tmp_path / "A",
            b=tmp_path / "B",
            workspace=tmp_path / "sessions" / "123",
            profile_name="default",
            profile={},
        )


def test_session_meta_rejects_invalid_session_id(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="invalid session id"):
        SessionMeta(
            session_id="../bad",
            status="created",
            created_at=datetime.now(timezone.utc),
            a=tmp_path / "A",
            b=tmp_path / "B",
            workspace=tmp_path / "sessions" / "bad",
            profile_name="default",
            profile={},
        )
