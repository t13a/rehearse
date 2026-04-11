"""Tests for rehearse.validate.preflight."""

from __future__ import annotations

from pathlib import Path

import pytest

from rehearse import validate


def test_preflight_ok(fake_ab: tuple[Path, Path]) -> None:
    a, b = fake_ab
    validate.preflight(a, b)


def test_preflight_a_missing(tmp_path: Path) -> None:
    b = tmp_path / "B"
    b.mkdir()
    with pytest.raises(validate.PreflightError, match="A does not exist"):
        validate.preflight(tmp_path / "A", b)


def test_preflight_a_not_dir(tmp_path: Path) -> None:
    a = tmp_path / "A"
    a.write_text("i am a file")
    b = tmp_path / "B"
    b.mkdir()
    with pytest.raises(validate.PreflightError, match="A is not a directory"):
        validate.preflight(a, b)


def test_preflight_rejects_symlink_in_a(tmp_path: Path) -> None:
    a = tmp_path / "A"
    a.mkdir()
    (a / "real.txt").write_text("x")
    (a / "link.txt").symlink_to(a / "real.txt")
    b = tmp_path / "B"
    b.mkdir()
    with pytest.raises(validate.PreflightError, match="A contains a symlink"):
        validate.preflight(a, b)


def test_preflight_rejects_symlink_in_b(tmp_path: Path) -> None:
    a = tmp_path / "A"
    a.mkdir()
    b = tmp_path / "B"
    b.mkdir()
    (b / "real.txt").write_text("x")
    (b / "link.txt").symlink_to(b / "real.txt")
    with pytest.raises(validate.PreflightError, match="B contains a symlink"):
        validate.preflight(a, b)


def test_preflight_b_missing(tmp_path: Path) -> None:
    a = tmp_path / "A"
    a.mkdir()
    with pytest.raises(validate.PreflightError, match="B does not exist"):
        validate.preflight(a, tmp_path / "B")
