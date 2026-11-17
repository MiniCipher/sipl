"""SEM-02: evaluation of the term on a state, rule trace, undefinedness."""

from __future__ import annotations

import pytest

from sipl.parser import parse_program
from sipl.semantics import build_term, evaluate, format_state, parse_state
from sipl.semantics.evaluator import PROGRAM_RULES, EvalResult
from sipl.semantics.state import StateFormatError


def run(src: str, state: dict[str, int] | None = None, **kw: int) -> EvalResult:
    return evaluate(build_term(parse_program(src)), state or {}, **kw)


def test_power(power_source: str) -> None:
    res = run(power_source, {"X": 2, "Y": 3})
    assert res.defined
    assert res.final == {"X": 2, "Y": 0, "R": 8}
    assert res.initial == {"X": 2, "Y": 3}
    # R := 1 then 3 iterations x 2 assignments
    assert len(res.transitions) == 7
    assert [t.var for t in res.transitions] == ["R", "R", "Y", "R", "Y", "R", "Y"]
    assert res.states[-1] == res.final


@pytest.mark.parametrize("src, state, final", [
    ("X := 7 / 2", {}, {"X": 3}),
    ("X := 0 - 7 / 2", {}, {"X": -3}),
    ("X := (0 - 7) / 2", {}, {"X": -3}),
    ("X := (0 - 7) / (0 - 2)", {}, {"X": 3}),
    ("X := 2 * 3 + 4", {}, {"X": 10}),
    ("skip", {"A": 1}, {"A": 1}),
    ("if 1 <> 1 then X := 1 else X := 2", {}, {"X": 2}),
    ("while X < 5 do X := X + 2", {"X": 0}, {"X": 6}),
])
def test_values(src: str, state: dict[str, int], final: dict[str, int]) -> None:
    res = run(src, state)
    assert res.defined and res.final == final


def test_state_is_not_mutated() -> None:
    state = {"X": 1}
    run("X := 5", state)
    assert state == {"X": 1}


def test_trace_rules_and_depths(power_source: str) -> None:
    res = run(power_source, {"X": 2, "Y": 1})
    rules = [e.rule for e in res.trace if e.rule in PROGRAM_RULES]
    assert rules == ["SEQ", "AS", "WH-T", "SEQ", "AS", "AS", "WH-F"]
    first = res.trace[0]
    assert first.depth == 0 and first.parent is None and first.state_in == 0
    assert first.state_out == len(res.states) - 1
    child = res.trace[1]
    assert child.parent == 0 and child.depth == 1
    assert "st0 ∇ [R ↦ 1]" in child.explanation
    assert all(e.explanation for e in res.trace)
    assert {e.rule for e in res.trace} >= {"DEN", "CONST", "ARITH", "REL"}


def test_if_rules() -> None:
    t = run("if X > 0 then Y := 1 else Y := 2", {"X": 1})
    f = run("if X > 0 then Y := 1 else Y := 2", {"X": 0})
    assert t.trace[0].rule == "IF-T" and f.trace[0].rule == "IF-F"
    assert t.final == {"X": 1, "Y": 1} and f.final == {"X": 0, "Y": 2}


def test_undefined_variable() -> None:
    res = run("Y := X + 1")
    assert not res.defined and res.final is None
    assert res.reason_code == "UNBOUND"
    assert "X" in (res.reason or "")
    assert res.trace[0].undefined
    den = [e for e in res.trace if e.rule == "DEN"][0]
    assert den.undefined and "X ∉ dom" in den.explanation
    assert res.error_ast_id is not None


def test_division_by_zero() -> None:
    res = run("Z := X / Y; W := 1", {"X": 1, "Y": 0})
    assert res.reason_code == "DIV_ZERO"
    assert not any(t.var == "W" for t in res.transitions)
    assert res.to_dict()["undefined"]["code"] == "DIV_ZERO"


def test_step_limit() -> None:
    res = run("while true do X := X + 1", {"X": 0}, max_steps=200)
    assert res.reason_code == "STEP_LIMIT"
    assert res.steps == 200
    assert len(res.transitions) > 5


@pytest.mark.parametrize("cond, expected", [
    ("Q > 0 or true", 1), ("true or Q > 0", 1), ("Q > 0 and false", 0), ("false and Q > 0", 0),
])
def test_kleene_logic(cond: str, expected: int) -> None:
    res = run(f"if {cond} then R := 1 else R := 0")
    assert res.defined and res.final == {"R": expected}


@pytest.mark.parametrize("cond", ["Q > 0 or false", "Q > 0 and true", "not (Q > 0)"])
def test_undefined_condition(cond: str) -> None:
    res = run(f"if {cond} then R := 1 else R := 0")
    assert not res.defined
    assert res.reason_code in {"UNBOUND", "UNDEFINED_CONDITION"}


def test_result_json(power_source: str) -> None:
    data = run(power_source, {"X": 3, "Y": 2}).to_dict()
    assert data["status"] == "defined" and data["final_state"]["R"] == 9
    assert data["transitions"][0]["var"] == "R"
    assert data["trace"][0]["rule"] == "SEQ"
    short = run(power_source, {"X": 3, "Y": 2}).to_dict(with_trace=False)
    assert "trace" not in short


def test_ascii_style() -> None:
    res = evaluate(build_term(parse_program("X := 1")), {}, style="ascii")
    assert "AS^X(#1)" in res.trace[0].explanation


@pytest.mark.parametrize("text, state", [
    ("X=2, Y=3", {"X": 2, "Y": 3}),
    ("X:=2 Y->-3", {"X": 2, "Y": -3}),
    ("[X ↦ 1, Y ↦ 2]", {"X": 1, "Y": 2}),
    ('{"A": 5}', {"A": 5}),
    ("", {}),
])
def test_parse_state(text: str, state: dict[str, int]) -> None:
    assert parse_state(text) == state


@pytest.mark.parametrize("text", ["X=abc", "{bad json", '{"X": "1"}', "[1, 2]", '{"X": true}'])
def test_parse_state_errors(text: str) -> None:
    with pytest.raises(StateFormatError):
        parse_state(text)


def test_format_state() -> None:
    assert format_state({"X": 1, "Y": 2}) == "[X ↦ 1, Y ↦ 2]"
    assert format_state({"X": 1}, "ascii") == "[X -> 1]"
    assert format_state(None) == "⊥"
