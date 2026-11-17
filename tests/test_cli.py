"""CLI integration tests: commands, output formats and stable exit codes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sipl import __version__
from sipl.cli import EXIT_OK, EXIT_SYNTAX, EXIT_UNDEFINED, EXIT_USAGE, main

from .conftest import EXAMPLES

POWER = str(EXAMPLES / "power.sipl")
BAD = str(EXAMPLES / "syntax_error.sipl")


def cli(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def test_check_ok(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "check", POWER)
    assert code == EXIT_OK and "OK" in out


def test_check_error(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = cli(capsys, "check", BAD)
    assert code == EXIT_SYNTAX
    assert "syntax_error.sipl:4:9" in err and "E104" in err


def test_check_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "check", BAD, "--json")
    data = json.loads(out)
    assert code == EXIT_SYNTAX and data["ok"] is False
    assert data["diagnostics"][0]["line"] == 4
    code, out, _ = cli(capsys, "check", POWER, "--json")
    assert json.loads(out)["variables"] == ["R", "Y", "X"]


@pytest.mark.parametrize("fmt, needle", [
    ("text", "Program"), ("json", '"type": "Program"'), ("sexpr", "(block (seq"),
    ("dot", "digraph"), ("svg", "<svg"),
])
def test_parse_formats(capsys: pytest.CaptureFixture[str], fmt: str, needle: str) -> None:
    code, out, _ = cli(capsys, "parse", POWER, "-f", fmt)
    assert code == EXIT_OK and needle in out


@pytest.mark.parametrize("fmt, needle", [
    ("text", "stmt_seq"), ("json", '"label": "program"'), ("dot", "digraph"), ("svg", "<svg"),
    ("html", "<!DOCTYPE html>"),
])
def test_tree_formats(capsys: pytest.CaptureFixture[str], fmt: str, needle: str) -> None:
    code, out, _ = cli(capsys, "tree", POWER, "-f", fmt)
    assert code == EXIT_OK and needle in out


def test_tree_to_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "t.svg"
    code, _, err = cli(capsys, "tree", POWER, "-f", "svg", "--compact", "-o", str(target))
    assert code == EXIT_OK and target.read_text("utf-8").startswith("<svg")
    assert str(target) in err


def test_term_variants(capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = cli(capsys, "term", POWER, "--style", "ascii")
    assert out.strip() == ("AS^R(#1) o WH(S^2(>, Y=>, #0), AS^R(S^2(*, R=>, X=>)) o "
                           "AS^Y(S^2(-, Y=>, #1)))")
    _, out, _ = cli(capsys, "term", POWER, "--steps")
    assert "[T-AS] ⟦R := 1⟧" in out
    _, out, _ = cli(capsys, "term", POWER, "--pretty", "--width", "30")
    assert len(out.strip().splitlines()) > 2
    _, out, _ = cli(capsys, "term", POWER, "--json")
    assert json.loads(out)["tree"]["kind"] == "COMP"
    for tree in ("text", "dot", "svg"):
        code, out, _ = cli(capsys, "term", POWER, "--tree", tree)
        assert code == EXIT_OK and out


def test_eval_defined(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "eval", POWER, "--state", "X=2, Y=3", "--explain", "-t")
    assert code == EXIT_OK
    assert "Результат: [X ↦ 2, Y ↦ 0, R ↦ 8]" in out
    assert "[WH-F]" in out and "[DEN]" not in out
    _, out, _ = cli(capsys, "eval", POWER, "-s", "X=2, Y=1", "-e", "-a", "--ascii")
    assert "[DEN]" in out and "[X -> 2, Y -> 0, R -> 2]" in out


def test_eval_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "eval", POWER, "-s", '{"X": 3, "Y": 2}', "--json")
    data = json.loads(out)
    assert code == EXIT_OK and data["final_state"] == {"X": 3, "Y": 0, "R": 9}
    assert data["trace"]


def test_eval_undefined(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "eval", str(EXAMPLES / "div_by_zero.sipl"), "-s", "X=1, Y=0")
    assert code == EXIT_UNDEFINED and "DIV_ZERO" in out
    code, out, _ = cli(capsys, "eval", str(EXAMPLES / "infinite_loop.sipl"),
                       "--max-steps", "300")
    assert code == EXIT_UNDEFINED and "STEP_LIMIT" in out and "ще" in out


def test_eval_inline_code(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "eval", "-c", "X := 6 * 7")
    assert code == EXIT_OK and "[X ↦ 42]" in out


def test_visualize(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "v.html"
    code, out, _ = cli(capsys, "visualize", POWER, "-s", "X=2,Y=2", "-o", str(target))
    assert code == EXIT_OK and target.exists()
    assert '"status": "defined"' in target.read_text("utf-8")


def test_analyze_report(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "analyze", POWER, "--state", '{"X": 2, "Y": 2}')
    data = json.loads(out)
    assert code == EXIT_OK and data["syntax_ok"] and data["schema"] == 1
    assert data["result"]["final_state"]["R"] == 4
    code, out, _ = cli(capsys, "analyze", BAD)
    assert code == EXIT_SYNTAX and json.loads(out)["diagnostics"][0]["code"] == "E104"


def test_grammar_command(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = cli(capsys, "grammar")
    assert code == EXIT_OK and "stmt_seq" in out
    assert cli(capsys, "grammar", POWER)[0] == EXIT_OK
    assert cli(capsys, "grammar", BAD)[0] == EXIT_SYNTAX


def test_usage_errors(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert cli(capsys, "check")[0] == EXIT_USAGE
    assert cli(capsys, "check", str(tmp_path / "missing.sipl"))[0] == EXIT_USAGE
    code, _, err = cli(capsys, "eval", POWER, "--state", "X=abc")
    assert code == EXIT_USAGE and "X=2" in err
    assert cli(capsys)[0] == EXIT_USAGE
    bin_file = tmp_path / "b.sipl"
    bin_file.write_bytes(b"\xff\xfe\x00")
    assert cli(capsys, "check", str(bin_file))[0] == EXIT_USAGE


def test_module_entry_point_and_version() -> None:
    out = subprocess.run([sys.executable, "-m", "sipl", "--version"], capture_output=True,
                         text=True)
    assert out.returncode == 0 and __version__ in out.stdout


def test_stdin(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("X := 1"))
    code, out, _ = cli(capsys, "check", "-")
    assert code == EXIT_OK and "<stdin>" in out
