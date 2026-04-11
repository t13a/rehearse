"""Shared pytest fixtures for rehearse tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from rehearse import config, docker


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "version"],
            check=True,
            capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


DOCKER_AVAILABLE = _docker_available()


@pytest.fixture
def docker_available() -> bool:
    if not DOCKER_AVAILABLE:
        pytest.skip("docker not available")
    return True


FAKE_RUNNER = Path(__file__).resolve().parent / "fake-runner.sh"


@pytest.fixture
def rehearse_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point REHEARSE_ROOT at a temp directory and refresh config.

    Also swaps REHEARSE_AGENT_RUNNER to a busybox-backed fake runner so that
    lifecycle tests don't need the real rehearse-agent image or an API key.
    """
    root = tmp_path / "rehearse"
    monkeypatch.setenv("REHEARSE_ROOT", str(root))
    monkeypatch.setenv("REHEARSE_AGENT_RUNNER", str(FAKE_RUNNER))
    monkeypatch.setenv("REHEARSE_AGENT_IMAGE", "busybox:latest")
    config.reload()
    yield root

    # Teardown: any session may contain agent-owned files under data/c/.
    # The harness UID cannot unlink them, so if the dir still exists we
    # need docker (running as root) to clean up.
    if root.exists():
        if DOCKER_AVAILABLE:
            try:
                docker.cleanup_container(root)
            except Exception:
                pass
        else:
            shutil.rmtree(root, ignore_errors=True)

    config.reload()


@pytest.fixture
def fake_ab(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal fake A and B pair on the same filesystem."""
    a = tmp_path / "A"
    b = tmp_path / "B"
    (a / "sub").mkdir(parents=True)
    (a / "file1.txt").write_text("hello\n")
    (a / "sub" / "file2.txt").write_text("world\n")

    (b / "existing").mkdir(parents=True)
    (b / "existing" / "old.txt").write_text("legacy\n")
    return a, b
