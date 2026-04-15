"""Tests for profile loading and default application."""

from __future__ import annotations

from pathlib import Path

import pytest

from rehearse import config, profile


def test_create_default_profile_file(
    rehearse_root: Path,
) -> None:
    default = config.PROFILES_DIR / "default.json"
    default.unlink()

    raw = profile.load_profile_for_create("default")

    assert raw == {}
    assert default.read_text() == "{}\n"


def test_load_named_profile(
    rehearse_root: Path,
) -> None:
    custom = config.PROFILES_DIR / "fast.json"
    custom.write_text('{"agent_image": "custom:latest", "agent_timeout": 30}\n')

    raw = profile.load_profile_for_create("fast")
    effective = profile.effective_profile(raw)

    assert raw == {"agent_image": "custom:latest", "agent_timeout": 30}
    assert effective.agent_image == "custom:latest"
    assert effective.agent_timeout == 30


def test_missing_non_default_profile_errors(
    rehearse_root: Path,
) -> None:
    with pytest.raises(profile.ProfileError, match="profile not found"):
        profile.load_profile_for_create("missing")


def test_invalid_profile_name_errors() -> None:
    with pytest.raises(profile.ProfileError, match="invalid profile name"):
        profile.load_profile_for_create("../bad")


def test_invalid_profile_json_errors(
    rehearse_root: Path,
) -> None:
    bad = config.PROFILES_DIR / "bad.json"
    bad.write_text("{bad json")

    with pytest.raises(profile.ProfileError, match="invalid profile JSON"):
        profile.load_profile_for_create("bad")


def test_invalid_profile_type_errors(
    rehearse_root: Path,
) -> None:
    bad = config.PROFILES_DIR / "badtype.json"
    bad.write_text('{"agent_uid": "not-an-int"}\n')

    with pytest.raises(profile.ProfileError, match="invalid profile"):
        profile.load_profile_for_create("badtype")


def test_relative_paths_resolve_from_rehearse_root(
    rehearse_root: Path,
) -> None:
    raw = {
        "agent_runner": "bin/runner.sh",
        "mcp_config": "mcp/config.json",
    }

    effective = profile.effective_profile(raw)

    assert effective.agent_runner == rehearse_root / "bin" / "runner.sh"
    assert effective.mcp_config == rehearse_root / "mcp" / "config.json"


def test_skeleton_defaults_to_default(
    rehearse_root: Path,
) -> None:
    assert profile.effective_profile({}).skeleton == "default"
    assert profile.effective_profile({"skeleton": None}).skeleton == "default"


def test_invalid_skeleton_name_errors(
    rehearse_root: Path,
) -> None:
    with pytest.raises(profile.ProfileError, match="invalid profile name"):
        profile.effective_profile({"skeleton": "../bad"})
