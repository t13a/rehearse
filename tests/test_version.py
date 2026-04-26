from __future__ import annotations

from importlib.metadata import version

from rehearse import __version__, cli


def test_package_version_comes_from_project_metadata() -> None:
    assert __version__ == version("rehearse")


def test_version_command_prints_package_version(
    capsys,
) -> None:
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out == f"rehearse {__version__}\n"
