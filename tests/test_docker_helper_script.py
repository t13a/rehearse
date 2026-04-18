"""Verify the docker-helper.sh shell contract."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from script_helpers import REPO_ROOT, write_executable


def test_docker_helper_assembles_root_helper_container(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_dump = tmp_path / "docker.argv"
    write_executable(
        bin_dir / "docker",
        "#!/bin/bash\n"
        "printf '%s\\n' \"$@\" > \"$DOCKER_ARGV_DUMP\"\n",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "DOCKER_ARGV_DUMP": str(argv_dump),
            "REHEARSE_HELPER_IMAGE": "busybox:test",
            "REHEARSE_HELPER_MOUNT": str(tmp_path / "sessions"),
        }
    )

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "docker-helper.sh"),
            "chown",
            "-Rh",
            "10000:10000",
            str(tmp_path / "sessions" / "123" / "home" / "agent"),
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    argv = argv_dump.read_text().splitlines()
    assert argv == [
        "run",
        "--rm",
        "--user",
        "0:0",
        "-v",
        f"{tmp_path / 'sessions'}:{tmp_path / 'sessions'}:rw",
        "busybox:test",
        "chown",
        "-Rh",
        "10000:10000",
        str(tmp_path / "sessions" / "123" / "home" / "agent"),
    ]
