"""rehearse: symlink-staging harness for large-file organization."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("rehearse")
except PackageNotFoundError:
    __version__ = "0+unknown"
