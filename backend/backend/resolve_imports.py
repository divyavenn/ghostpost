"""Helpers for running backend modules directly.

These utilities let modules that expect to be imported as part of the
`backend` package run as standalone scripts (e.g. `python read_tweets.py`).
"""

from __future__ import annotations

import sys
from collections.abc import MutableMapping
from pathlib import Path


def ensure_standalone_imports(
    module_globals: MutableMapping[str, object],
    package_name: str | None = None,
) -> None:
    """Enable relative imports when a module runs as a script.

    This mirrors the recommendation from PEP 366: we add the parent directory
    of the package to ``sys.path`` and populate ``__package__`` so that
    ``from . import sibling`` style imports keep working.
    """

    file_path = Path(str(module_globals["__file__"]))
    package_dir = file_path.resolve().parent
    parent_dir = package_dir.parent

    parent_as_str = str(parent_dir)
    if parent_as_str not in sys.path:
        sys.path.insert(0, parent_as_str)

    if module_globals.get("__package__") not in (None, ""):
        return

    package = package_name or package_dir.name
    module_globals["__package__"] = package
