"""Verify the env-var contract between helper functions and docker-helper.sh."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from rehearse import config, helper
from rehearse.profile import effective_profile


def _make_dump_helper(tmp_path: Path, dump_path: Path) -> Path:
    script = tmp_path / "dump-helper.sh"
    script.write_text(
        "#!/bin/bash\n"
        f"env > {dump_path}.env\n"
        f"printf '%s\\n' \"$@\" > {dump_path}.argv\n"
    )
    script.chmod(
        script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return script


def _parse_env(dump_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in dump_path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def test_chown_paths_invokes_docker_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dump = tmp_path / "helper.dump"
    script = _make_dump_helper(tmp_path, dump)
    monkeypatch.setattr(config, "DEFAULT_DOCKER_HELPER", script)

    effective = effective_profile({"helper_image": "busybox:test"})
    session_dir = tmp_path / "sessions" / "123"
    inbox = session_dir / "data" / "inbox"
    home = session_dir / "home" / "agent"

    helper.chown_paths(
        session_dir.parent,
        [inbox, home],
        effective,
        uid=12345,
        gid=23456,
    )

    env = _parse_env(Path(f"{dump}.env"))
    argv = Path(f"{dump}.argv").read_text().splitlines()
    assert env["REHEARSE_HELPER_IMAGE"] == "busybox:test"
    assert env["REHEARSE_HELPER_MOUNT"] == str(session_dir.parent)
    assert argv == [
        "chown",
        "-Rh",
        "12345:23456",
        str(inbox),
        str(home),
    ]


def test_remove_tree_invokes_docker_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dump = tmp_path / "helper.dump"
    script = _make_dump_helper(tmp_path, dump)
    monkeypatch.setattr(config, "DEFAULT_DOCKER_HELPER", script)

    effective = effective_profile({"helper_image": "busybox:test"})
    session_dir = tmp_path / "sessions" / "123"

    helper.remove_tree(session_dir.parent, session_dir, effective)

    env = _parse_env(Path(f"{dump}.env"))
    argv = Path(f"{dump}.argv").read_text().splitlines()
    assert env["REHEARSE_HELPER_IMAGE"] == "busybox:test"
    assert env["REHEARSE_HELPER_MOUNT"] == str(session_dir.parent)
    assert argv == ["rm", "-rf", str(session_dir)]
