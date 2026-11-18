#!/usr/bin/env python3
"""SIPL conformance suite runner (CORE-06).

Implementation-independent: it imports nothing from the `sipl` package and
talks to the implementation under test only through a command line adapter
(see conformance/README.md for the protocol). Standard library only.

Usage:
    python conformance/run_conformance.py                      # tests `sipl analyze`
    python conformance/run_conformance.py --impl "python -m sipl analyze"
    python conformance/run_conformance.py --filter power -v
    python conformance/run_conformance.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_IMPL = "sipl analyze"


def _norm_sexpr(text: str) -> str:
    return " ".join(text.replace("(", " ( ").replace(")", " ) ").split())


def _norm_term(text: str) -> str:
    return "".join(text.split())


def call_impl(impl: list[str], case_file: Path, state: dict[str, int] | None,
              max_steps: int | None, timeout: float, strict: bool = False) -> dict[str, Any]:
    cmd = impl + [str(case_file)]
    if strict:
        cmd.append("--strict")
    if state is not None:
        cmd += ["--state", json.dumps(state)]
    if max_steps is not None:
        cmd += ["--max-steps", str(max_steps)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"adapter did not return JSON (exit {proc.returncode}): "
                           f"{proc.stdout[:200]!r} {proc.stderr[:300]!r}") from None
    if not isinstance(data, dict):
        raise RuntimeError("adapter output is not a JSON object")
    return data


def check_case(impl: list[str], sipl: Path, expect: dict[str, Any],
               timeout: float) -> list[str]:
    """Return a list of failure messages (empty = passed)."""
    failures: list[str] = []
    report = call_impl(impl, sipl, None, None, timeout)
    syntax_ok = bool(report.get("syntax_ok"))
    want_ok = expect.get("syntax", "ok") == "ok"
    if syntax_ok != want_ok:
        diags = report.get("diagnostics") or []
        detail = f": {diags[0].get('message')}" if diags else ""
        return [f"syntax: expected {'ok' if want_ok else 'error'}, got "
                f"{'ok' if syntax_ok else 'error'}{detail}"]
    if not want_ok:
        err = expect.get("error")
        if err:
            diags = report.get("diagnostics") or []
            if not diags:
                failures.append("expected a diagnostic, got none")
            else:
                d = diags[0]
                if (d.get("line"), d.get("column")) != (err["line"], err["column"]):
                    failures.append(f"error position: expected {err['line']}:{err['column']}, "
                                    f"got {d.get('line')}:{d.get('column')} ({d.get('message')})")
        return failures
    lang = expect.get("language")
    if lang in ("core", "extension"):
        strict = call_impl(impl, sipl, None, None, timeout, strict=True)
        if bool(strict.get("syntax_ok")) != (lang == "core"):
            what = ("core language must be accepted" if lang == "core"
                    else "extended language must be rejected")
            failures.append(f"--strict: a program of the {what}")
    if "ast" in expect and _norm_sexpr(report.get("ast") or "") != _norm_sexpr(expect["ast"]):
        failures.append(f"ast:\n      expected {expect['ast']}\n      got      {report.get('ast')}")
    if "term" in expect and _norm_term(report.get("term") or "") != _norm_term(expect["term"]):
        failures.append(f"term:\n      expected {expect['term']}\n      got      {report.get('term')}")
    for i, run in enumerate(expect.get("runs", []), 1):
        rep = call_impl(impl, sipl, run.get("state", {}), run.get("max_steps"), timeout)
        result = rep.get("result") or {}
        status = result.get("status")
        if status != run["result"]:
            failures.append(f"run {i} {run.get('state')}: expected {run['result']}, got {status}"
                            f" ({(result.get('undefined') or {}).get('reason', '')})")
            continue
        if run["result"] == "defined" and result.get("final_state") != run["final_state"]:
            failures.append(f"run {i} {run.get('state')}: expected final state "
                            f"{run['final_state']}, got {result.get('final_state')}")
        code = run.get("undefined_code")
        if run["result"] == "undefined" and code:
            got = (result.get("undefined") or {}).get("code")
            if got != code:
                failures.append(f"run {i}: expected undefinedness {code}, got {got}")
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cases", nargs="?", default=str(HERE / "cases"), help="directory with cases")
    ap.add_argument("--impl", default=DEFAULT_IMPL,
                    help=f"adapter command of the implementation (default: '{DEFAULT_IMPL}')")
    ap.add_argument("--filter", default="", help="run only cases whose name contains this")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--json", metavar="FILE", help="write a machine-readable report")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    impl = shlex.split(args.impl, posix=(sys.platform != "win32"))
    cases = sorted(p for p in Path(args.cases).glob("*.sipl") if args.filter in p.stem)
    if not cases:
        print("no cases found", file=sys.stderr)
        return 2
    results = []
    started = time.time()
    passed = 0
    for sipl in cases:
        expect_file = sipl.with_name(sipl.stem + ".expect.json")
        expect = json.loads(expect_file.read_text(encoding="utf-8"))
        try:
            failures = check_case(impl, sipl, expect, args.timeout)
        except Exception as exc:  # adapter crashed / timed out
            failures = [f"adapter error: {exc}"]
        ok = not failures
        passed += ok
        results.append({"case": sipl.stem, "category": expect.get("category"), "passed": ok,
                        "failures": failures})
        if not ok or args.verbose:
            print(f"{'PASS' if ok else 'FAIL'}  {sipl.stem}")
            for f in failures:
                print(f"      {f}")
    total = len(cases)
    print(f"\nconformance: {passed}/{total} passed ({time.time() - started:.1f}s), "
          f"implementation: {args.impl}")
    if args.json:
        Path(args.json).write_text(json.dumps({"passed": passed, "total": total,
                                               "results": results}, indent=2), encoding="utf-8")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
