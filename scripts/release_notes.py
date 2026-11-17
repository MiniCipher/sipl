#!/usr/bin/env python3
"""Print the CHANGELOG.md section of the given version (used by the release workflow)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def notes(version: str, changelog: str) -> str:
    version = version.lstrip("v")
    pattern = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", re.M | re.S)
    m = pattern.search(changelog)
    if not m:
        raise SystemExit(f"version {version} not found in CHANGELOG.md")
    return m.group(1).strip() + "\n"


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(notes(sys.argv[1], (root / "CHANGELOG.md").read_text("utf-8")), end="")
