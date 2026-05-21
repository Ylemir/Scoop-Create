"""scoop-create - Generate Scoop app manifests from GitHub repository URLs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("scoop-create")
except PackageNotFoundError:
    __version__ = "dev"
