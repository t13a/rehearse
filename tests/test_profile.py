"""Tests for profile loading and default application."""

from __future__ import annotations

import os
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


def test_agent_defaults_to_codex(
    rehearse_root: Path,
) -> None:
    effective = profile.effective_profile({})

    assert effective.agent == "codex"
    assert effective.agent_runner == config.DEFAULT_AGENT_RUNNER
    assert effective.agent_image == config.DEFAULT_CODEX_AGENT_IMAGE

    explicit_null = profile.effective_profile({"agent": None})
    assert explicit_null.agent == "codex"
    assert explicit_null.agent_runner == config.DEFAULT_AGENT_RUNNER
    assert explicit_null.agent_image == config.DEFAULT_CODEX_AGENT_IMAGE


def test_uid_gid_defaults_to_host_agent_and_nobody_guard(
    rehearse_root: Path,
) -> None:
    effective = profile.effective_profile({})

    assert effective.agent_uid == os.getuid()
    assert effective.agent_gid == os.getgid()
    assert effective.guard_uid == config.DEFAULT_GUARD_UID
    assert effective.guard_gid == config.DEFAULT_GUARD_GID


def test_uid_gid_overrides(
    rehearse_root: Path,
) -> None:
    effective = profile.effective_profile(
        {
            "agent_uid": 20000,
            "agent_gid": 30000,
            "guard_uid": 20001,
            "guard_gid": 30000,
        }
    )

    assert effective.agent_uid == 20000
    assert effective.agent_gid == 30000
    assert effective.guard_uid == 20001
    assert effective.guard_gid == 30000


def test_agent_uid_must_not_match_guard_uid(
    rehearse_root: Path,
) -> None:
    with pytest.raises(profile.ProfileError, match="agent_uid and guard_uid"):
        profile.effective_profile({"agent_uid": 20000, "guard_uid": 20000})


def test_codex_agent_selects_codex_defaults(
    rehearse_root: Path,
) -> None:
    effective = profile.effective_profile({"agent": "codex"})

    assert effective.agent == "codex"
    assert effective.agent_runner == config.DEFAULT_AGENT_RUNNER
    assert effective.agent_image == config.DEFAULT_CODEX_AGENT_IMAGE


def test_claude_agent_selects_claude_defaults(
    rehearse_root: Path,
) -> None:
    effective = profile.effective_profile({"agent": "claude"})

    assert effective.agent == "claude"
    assert effective.agent_runner == config.DEFAULT_AGENT_RUNNER
    assert effective.agent_image == config.DEFAULT_CLAUDE_AGENT_IMAGE


def test_agent_runner_and_image_override_agent_defaults(
    rehearse_root: Path,
) -> None:
    effective = profile.effective_profile(
        {
            "agent": "claude",
            "agent_runner": "bin/codex-wrapper.sh",
            "agent_image": "custom-codex:latest",
        }
    )

    assert effective.agent == "claude"
    assert effective.agent_runner == rehearse_root / "bin" / "codex-wrapper.sh"
    assert effective.agent_image == "custom-codex:latest"


def test_invalid_agent_errors(
    rehearse_root: Path,
) -> None:
    with pytest.raises(profile.ProfileError, match="use 'codex' or 'claude'"):
        profile.effective_profile({"agent": "bad-agent"})


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
    }

    effective = profile.effective_profile(raw)

    assert effective.agent_runner == rehearse_root / "bin" / "runner.sh"


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
