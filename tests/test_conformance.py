"""CORE-06: the conformance suite runs against the implementation through its CLI adapter."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from .conftest import CONFORMANCE

RUNNER = CONFORMANCE / "run_conformance.py"
IMPL = f'"{sys.executable}" -m sipl analyze' if sys.platform != "win32" else \
    f"{sys.executable} -m sipl analyze"


def run_suite(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(RUNNER), "--impl", IMPL, *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_case_files_are_well_formed() -> None:
    cases = sorted((CONFORMANCE / "cases").glob("*.sipl"))
    assert len(cases) >= 40
    categories = set()
    for c in cases:
        exp = json.loads(c.with_name(c.stem + ".expect.json").read_text("utf-8"))
        assert exp["syntax"] in ("ok", "error")
        categories.add(exp["category"])
        if exp["syntax"] == "error":
            assert set(exp["error"]) == {"line", "column"}
        for run in exp.get("runs", []):
            assert run["result"] in ("defined", "undefined")
            assert ("final_state" in run) == (run["result"] == "defined")
    assert categories == {"semantics", "undefined", "syntax-error"}


def test_full_suite_passes(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    proc = run_suite("--json", str(report))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(report.read_text("utf-8"))
    assert data["passed"] == data["total"] >= 40


def test_runner_detects_wrong_expectations(tmp_path: Path) -> None:
    src = CONFORMANCE / "cases"
    for name in ("001-assign-const", "033-err-trailing-semicolon"):
        for ext in (".sipl", ".expect.json"):
            shutil.copy(src / f"{name}{ext}", tmp_path / f"{name}{ext}")
    broken = tmp_path / "001-assign-const.expect.json"
    exp = json.loads(broken.read_text("utf-8"))
    exp["runs"][0]["final_state"] = {"X": 6}
    exp["ast"] = "(assign X (num 6))"
    broken.write_text(json.dumps(exp), encoding="utf-8")
    err = tmp_path / "033-err-trailing-semicolon.expect.json"
    exp = json.loads(err.read_text("utf-8"))
    exp["error"]["column"] = 1
    err.write_text(json.dumps(exp), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(RUNNER), str(tmp_path), "--impl", IMPL],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1
    assert "0/2 passed" in proc.stdout
    assert "expected final state" in proc.stdout and "error position" in proc.stdout


def test_runner_reports_broken_adapter(tmp_path: Path) -> None:
    shutil.copy(CONFORMANCE / "cases" / "002-skip.sipl", tmp_path)
    shutil.copy(CONFORMANCE / "cases" / "002-skip.expect.json", tmp_path)
    proc = subprocess.run([sys.executable, str(RUNNER), str(tmp_path), "--impl",
                           f'"{sys.executable}" -c "print(1)"'],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1 and "adapter" in proc.stdout
