"""REL-02 helpers: release notes extraction and tag/version check."""

from __future__ import annotations

import subprocess
import sys

from sipl import __version__

from .conftest import ROOT


def test_release_notes_for_current_version() -> None:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "release_notes.py"),
                          f"v{__version__}"], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert "CORE-01" in out.stdout and "## [" not in out.stdout


def test_release_notes_unknown_version() -> None:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "release_notes.py"), "v9.9.9"],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode != 0


def test_version_check() -> None:
    script = str(ROOT / "scripts" / "check_version.py")
    ok = subprocess.run([sys.executable, script, f"v{__version__}"], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    bad = subprocess.run([sys.executable, script, "v0.0.1"], capture_output=True, text=True)
    assert bad.returncode != 0
