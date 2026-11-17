#!/usr/bin/env python3
"""Fail if the git tag (v1.2.3) differs from the version in pyproject.toml / sipl.__version__."""

from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tag = sys.argv[1].lstrip("v")
pyproject = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text("utf-8"), re.M)
init = re.search(r'__version__ = "([^"]+)"', (root / "src/sipl/__init__.py").read_text("utf-8"))
found = {pyproject.group(1) if pyproject else None, init.group(1) if init else None}
if found != {tag}:
    sys.exit(f"tag v{tag} does not match package version(s) {sorted(map(str, found))}")
if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", tag):
    sys.exit(f"tag v{tag} is not a SemVer version")
print(f"version {tag} OK")
