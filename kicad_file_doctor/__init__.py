"""kicad-file-doctor: explain why KiCad rejects or mis-loads a file."""

from .checks import Finding, diagnose

__version__ = "0.1.0"

__all__ = ["Finding", "diagnose", "__version__"]
