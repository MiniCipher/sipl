"""SEM-02: application of the term to a state by the formulas of table 1.5."""

from __future__ import annotations

import pytest

from sipl.parser import parse_program
from sipl.semantics import build_term, evaluate, format_state, parse_state
from sipl.semantics.evaluator import PROGRAM_RULES, RULE_DESCRIPTIONS, EvalResult
from sipl.semantics.state import StateFormatError

from .conftest import prog

GCD = "begin\n while ¬M=N do\n  if M>N then M:=M–N else N:=N–M\nend"


def run(body: str, state: dict[str, int] | None = None, **kw: int) -> EvalResult:
    src = body if body.lstrip().startswith("begin") else prog(body)
    return evaluate(build_term(parse_program(src)), state or {}, **kw)


def test_practicum_power_x5_y2(power_source: str) -> None:
    # practical work 2: st = [X ↦ 5, Y ↦ 2]  ->  R = 25
    res = run(power_source, {"X": 5, "Y": 2})
    assert res.defined
    assert res.final == {"X": 5, "Y": 0, "R": 25}
    assert [t.var for t in res.transitions] == ["R", "R", "Y", "R", "Y"]
    assert [t.value for t in res.transitions] == [1, 5, 1, 25, 0]
    assert res.states[-1] == res.final


def test_textbook_example_1_4_gcd() -> None:
    # WH(...)([M ↦ 8, N ↦ 16]) = [M ↦ 8, N ↦ 8]
    res = run(GCD, {"M": 8, "N": 16})
    assert res.final == {"M": 8, "N": 8}
    s = [e for e in res.trace if e.rule == "AF_S"]
    assert s[0].explanation.endswith("neg(false) = true")
    assert "eq(M⇒(st0), N⇒(st0)) = eq(8, 16) = false" in s[1].explanation


@pytest.mark.parametrize("src, state, final", [
    ("X := 2 * 3 + 4", {}, {"X": 10}),
    ("X := -7 + 2", {}, {"X": -5}),
    ("skip", {"A": 1}, {"A": 1}),
    ("if 1 = 2 then X := 1 else X := 2", {}, {"X": 2}),
    ("while 5 > X do X := X + 2", {"X": 0}, {"X": 6}),
    ("X := 7 div 2; Y := 7 mod 2", {}, {"X": 3, "Y": 1}),
    ("X := -7 div 2; Y := -7 mod 2", {}, {"X": -4, "Y": 1}),
    ("if 1 < 2 and 2 <= 2 and 1 <> 2 and 3 >= 3 and true then X := 1 else X := 0", {}, {"X": 1}),
])
def test_values(src: str, state: dict[str, int], final: dict[str, int]) -> None:
    res = run(src, state)
    assert res.defined and res.final == final


def test_overlay_keeps_order() -> None:
    # [M ↦ 8, N ↦ 16] ∇ [M ↦ 3, X ↦ 4] = [M ↦ 3, N ↦ 16, X ↦ 4]
    res = run("M := 3; X := 4", {"M": 8, "N": 16})
    assert list(res.final or {}) == ["M", "N", "X"]
    assert res.final == {"M": 3, "N": 16, "X": 4}


def test_state_is_not_mutated() -> None:
    state = {"X": 1}
    run("X := 5", state)
    assert state == {"X": 1}


def test_trace_uses_textbook_formulas(power_source: str) -> None:
    res = run(power_source, {"X": 2, "Y": 1})
    rules = [e.rule for e in res.trace if e.rule in PROGRAM_RULES]
    # SEQ, AS(R:=1), WH (whole loop), WH iteration 1, SEQ, AS, AS, WH exit check
    assert rules == ["AF_SEQ", "AF_AS", "AF_WH", "AF_WH", "AF_SEQ", "AF_AS", "AF_AS", "AF_WH"]
    assert {e.rule for e in res.trace} <= set(RULE_DESCRIPTIONS)
    first = res.trace[0]
    assert first.depth == 0 and first.parent is None and first.state_in == 0
    assert first.state_out == len(res.states) - 1
    assign = res.trace[1]
    assert assign.parent == 0 and assign.depth == 1
    assert "st0 ∇ [R ↦ 1̅(st0)] = st0 ∇ [R ↦ 1]" in assign.explanation
    loop = [e for e in res.trace if e.rule == "AF_WH"][0]
    assert loop.note == "NumItWH = 1"
    gr = [e for e in res.trace if e.rule == "AF_S"][0]
    assert gr.explanation == "S²(gr, Y⇒, 0̅)(st1) = gr(Y⇒(st1), 0̅(st1)) = gr(1, 0) = true"
    den = [e for e in res.trace if e.rule == "AF_DNM"][0]
    assert den.explanation == "Y⇒(st1) = st1(Y) = 1"
    assert all(e.explanation for e in res.trace)


def test_loop_without_iterations() -> None:
    res = run("while X > 0 do X := X - 1", {"X": 0})
    loop = res.trace[0]
    assert loop.rule == "AF_WH" and loop.note == "NumItWH = 0"
    assert "жодної ітерації" in loop.explanation


def test_if_branches() -> None:
    t = run("if X > 0 then Y := 1 else Y := 2", {"X": 1})
    f = run("if X > 0 then Y := 1 else Y := 2", {"X": 0})
    assert t.trace[0].note == "fb = true" and "fs1(st0)" in t.trace[0].explanation
    assert f.trace[0].note == "fb = false" and "fs2(st0)" in f.trace[0].explanation
    assert t.final == {"X": 1, "Y": 1} and f.final == {"X": 0, "Y": 2}


def test_undefined_dename() -> None:
    res = run("Y := X + 1")
    assert not res.defined and res.final is None
    assert res.reason_code == "UNBOUND"
    assert "X⇒(st0) не визначене" in (res.reason or "")
    assert res.trace[0].undefined
    den = [e for e in res.trace if e.rule == "AF_DNM"][0]
    assert den.undefined and "не має значення" in den.explanation
    assert res.error_ast_id is not None


@pytest.mark.parametrize("cond", ["(Q > 0) ∨ (1 = 1)", "(1 = 1) ∨ (Q > 0)", "¬(Q = 1)",
                                  "Q > 0 and false"])
def test_strict_partiality(cond: str) -> None:
    # Remark 1.6: if any function in the formula is undefined, so is the result
    res = run(f"if {cond} then R := 1 else R := 0")
    assert not res.defined and res.reason_code == "UNBOUND"


def test_division_by_zero() -> None:
    res = run("Z := X div Y; W := 1", {"X": 1, "Y": 0})
    assert res.reason_code == "DIV_ZERO"
    assert not any(t.var == "W" for t in res.transitions)
    assert res.to_dict()["undefined"]["code"] == "DIV_ZERO"
    assert run("Z := 1 mod 0").reason_code == "DIV_ZERO"


def test_step_limit() -> None:
    res = run("while 1 = 1 do X := X + 1", {"X": 0}, max_steps=200)
    assert res.reason_code == "STEP_LIMIT"
    assert res.steps == 200
    assert len(res.transitions) > 5
    assert res.trace[0].undefined and "NumItWH" in (res.reason or "")


def test_result_json(power_source: str) -> None:
    data = run(power_source, {"X": 3, "Y": 2}).to_dict()
    assert data["status"] == "defined" and data["final_state"]["R"] == 9
    assert data["transitions"][0]["var"] == "R"
    assert data["trace"][0]["rule"] == "AF_SEQ"
    assert "trace" not in run(power_source, {"X": 3, "Y": 2}).to_dict(with_trace=False)


def test_ascii_style() -> None:
    res = evaluate(build_term(parse_program(prog("X := 1"))), {}, style="ascii")
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
