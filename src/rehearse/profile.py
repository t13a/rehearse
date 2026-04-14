"""Profile loading and default application."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from rehearse import config


PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class ProfileError(RuntimeError):
    """Raised when a profile cannot be loaded or validated."""


class RawProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_uid: int | None = None
    agent_gid: int | None = None
    agent_image: str | None = None
    helper_image: str | None = None
    agent_runner: Path | None = None
    agent_timeout: int | None = None
    mcp_config: Path | None = None
    agent_extra_args: str | None = None


class EffectiveProfile(BaseModel):
    agent_uid: int
    agent_gid: int
    agent_image: str
    helper_image: str
    agent_runner: Path
    agent_timeout: int
    mcp_config: Path | None
    agent_extra_args: str | None


def validate_name(name: str) -> None:
    if not PROFILE_NAME_RE.fullmatch(name):
        raise ProfileError(
            "invalid profile name: use only letters, digits, '_', '-', and '.'"
        )


def profile_path(name: str) -> Path:
    validate_name(name)
    return config.PROFILES_DIR / f"{name}.json"


def ensure_default_profile() -> None:
    path = profile_path("default")
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n")


def load_raw_profile(name: str) -> dict[str, Any]:
    path = profile_path(name)
    if not path.exists():
        raise ProfileError(f"profile not found: {name}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ProfileError(f"invalid profile JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ProfileError(f"profile must be a JSON object: {path}")
    try:
        RawProfile.model_validate(data)
    except ValidationError as e:
        raise ProfileError(f"invalid profile {name}: {e}") from e
    return data


def load_profile_for_create(name: str) -> dict[str, Any]:
    if name == "default":
        ensure_default_profile()
    return load_raw_profile(name)


def _resolve_root_relative(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path
    return config.REHEARSE_ROOT / path


def effective_profile(raw: dict[str, Any]) -> EffectiveProfile:
    try:
        profile = RawProfile.model_validate(raw)
    except ValidationError as e:
        raise ProfileError(f"invalid session profile: {e}") from e

    agent_runner = (
        config.DEFAULT_AGENT_RUNNER
        if profile.agent_runner is None
        else _resolve_root_relative(profile.agent_runner)
    )
    mcp_config = (
        None
        if profile.mcp_config is None
        else _resolve_root_relative(profile.mcp_config)
    )

    return EffectiveProfile(
        agent_uid=(
            config.DEFAULT_AGENT_UID if profile.agent_uid is None else profile.agent_uid
        ),
        agent_gid=(
            config.DEFAULT_AGENT_GID if profile.agent_gid is None else profile.agent_gid
        ),
        agent_image=(
            config.DEFAULT_AGENT_IMAGE
            if profile.agent_image is None
            else profile.agent_image
        ),
        helper_image=(
            config.DEFAULT_HELPER_IMAGE
            if profile.helper_image is None
            else profile.helper_image
        ),
        agent_runner=agent_runner,
        agent_timeout=(
            config.DEFAULT_AGENT_TIMEOUT
            if profile.agent_timeout is None
            else profile.agent_timeout
        ),
        mcp_config=mcp_config,
        agent_extra_args=profile.agent_extra_args,
    )
