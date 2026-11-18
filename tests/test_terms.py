"""SEM-01: construction of semantic terms by the rules of the textbook (table 1.6)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sipl.parser import parse, parse_program
from sipl.semantics import build_term, build_term_with_steps, render_pretty, render_text
from sipl.semantics.builder import EXTENSION_RULES, RULE_SCHEMES
from sipl.semantics.terms import AssignT, CompT, ConstT, DenameT, IdT, IfT, SuperT, WhileT

from .conftest import EXAMPLES, prog

GOLDEN = Path(__file__).parent / "golden"
EXAMPLE_FILES = sorted(p for p in EXAMPLES.glob("*.sipl") if p.stem != "syntax_error")


def term_of(body: str, style: str = "ascii") -> str:
    return render_text(build_term(parse_program(prog(body))), style)


@pytest.mark.parametrize("source, expected", [
    ("X := 1", "AS^X(#1)"),
    ("X := -1", "AS^X(#-1)"),
    ("skip", "id"),
    ("X := Y", "AS^X(Y=>)"),
    ("X := 1; Y := 2", "AS^X(#1) o AS^Y(#2)"),
    ("begin X := 1 end", "AS^X(#1)"),
    ("X := A - B * 2", "AS^X(S^2(sub, A=>, S^2(mult, B=>, #2)))"),
    ("X := (A + B)", "AS^X(S^2(add, A=>, B=>))"),
    ("if X = 1 then skip else X := 0", "IF(S^2(eq, X=>, #1), id, AS^X(#0))"),
    ("while ¬(X > 1) do X := X + 1", "WH(S^1(neg, S^2(gr, X=>, #1)), AS^X(S^2(add, X=>, #1)))"),
    ("if X = 1 ∨ X > 2 then skip else skip", "IF(S^2(or, S^2(eq, X=>, #1), S^2(gr, X=>, #2)), id, id)"),
    # extensions
    ("X := A div B mod 2", "AS^X(S^2(mod, S^2(div, A=>, B=>), #2))"),
    ("if X >= 1 and true then skip else skip", "IF(S^2(and, S^2(gre, X=>, #1), #true), id, id)"),
    ("if X < 1 or X <= 2 or X <> 3 then skip else skip",
     "IF(S^2(or, S^2(or, S^2(less, X=>, #1), S^2(leq, X=>, #2)), S^2(neq, X=>, #3)), id, id)"),
])
def test_construction_rules(source: str, expected: str) -> None:
    assert term_of(source) == expected


def test_textbook_example_1_2() -> None:
    # sem_A(X+Y*Z) = S2(add, X⇒, S2(mult, Y⇒, Z⇒))
    assert term_of("R := X + Y * Z", "unicode") == "AS^R(S²(add, X⇒, S²(mult, Y⇒, Z⇒)))"


def test_textbook_example_1_3_gcd() -> None:
    src = "begin\n while ¬M=N do\n  if M>N then M:=M–N else N:=N–M\nend"
    assert render_text(build_term(parse_program(src)), "unicode") == (
        "WH(S¹(neg, S²(eq, M⇒, N⇒)), IF(S²(gr, M⇒, N⇒), AS^M(S²(sub, M⇒, N⇒)), "
        "AS^N(S²(sub, N⇒, M⇒))))")


def test_practicum_power_term(power_source: str) -> None:
    # ASR(1̄) · WH(S2(gr, Y⇒, 0̄), ASR(S2(mult, R⇒, X⇒)) · ASY(S2(sub, Y⇒, 1̄)))
    text = render_text(build_term(parse_program(power_source)), "unicode")
    assert text == ("AS^R(1̅) • WH(S²(gr, Y⇒, 0̅), AS^R(S²(mult, R⇒, X⇒)) • "
                    "AS^Y(S²(sub, Y⇒, 1̅)))")


def test_latex_rendering() -> None:
    text = term_of("if X > 10 then X := X * 2 else skip", "latex")
    assert text == (r"\mathrm{IF}(S^{2}(\mathit{gr}, X\Rightarrow, \overline{10}), "
                    r"\mathrm{AS}^{X}(S^{2}(\mathit{mult}, X\Rightarrow, \overline{2})), "
                    r"\mathrm{id})")


def test_term_structure_and_links(power_source: str) -> None:
    program = parse_program(power_source)
    term = build_term(program)
    assert isinstance(term, CompT)
    first, loop = term.flatten()
    assert isinstance(first, AssignT) and isinstance(first.expr, ConstT)
    assert isinstance(loop, WhileT) and isinstance(loop.cond, SuperT)
    assert loop.cond.name == "gr"
    nodes = program.node_by_id()
    for t in term.walk():
        assert t.ast_id is not None
        expected = {"AS": "Assign", "COMP": "Seq", "WH": "While", "IF": "If", "ID": "Skip",
                    "CONST": "Num", "DEN": "Var", "BCONST": "BoolLit"}.get(t.kind)
        if expected:
            assert nodes[t.ast_id].kind == expected
    ids = [t.id for t in term.walk()]
    assert ids == list(range(len(ids)))


def test_sorts() -> None:
    term = build_term(parse_program(prog("if X > 1 then Y := X + 1 else skip")))
    assert isinstance(term, IfT)
    assert term.sort == "program"
    assert term.cond.sort == "predicate"
    assert isinstance(term.then, AssignT) and term.then.expr.sort == "function"
    assert isinstance(term.other, IdT)
    assert isinstance(list(build_term(parse_program(prog("X := Y"))).walk())[1], DenameT)


def test_construction_steps_follow_the_practicum(power_source: str) -> None:
    term, steps = build_term_with_steps(parse_program(power_source), power_source)
    rules = [s.rule for s in steps]
    # the same order as the derivation in practical work 2
    assert rules[:8] == ["NS_Prog", "NS_Stm_Seq", "NS_Stm_As", "NS_A_Num", "NS_Stm_Wh",
                         "NS_B_gr", "NS_A_Var", "NS_A_Num"]
    assert steps[0].lhs.startswith("sem_P(begin R := 1;")
    assert steps[0].rhs.startswith("sem_S(R := 1;")
    assert (steps[2].lhs, steps[2].rhs) == ("sem_S(R := 1)", "AS^R(sem_A(1))")
    assert steps[5].rhs == "S²(gr, sem_A(Y), sem_A(0))"
    assert "NS_Stm_BE" in rules and "NS_A_Mult" in rules and "NS_A_Sub" in rules
    assert steps[0].term is term
    assert all(s.rule in RULE_SCHEMES for s in steps)


def test_parenthesis_rules() -> None:
    src = prog("if ((X > 1)) then X := (1 + 2) else skip")
    _, steps = build_term_with_steps(parse_program(src), src)
    rules = [s.rule for s in steps]
    assert rules.count("NS_B_Par") == 2 and rules.count("NS_A_Par") == 1
    par = [s for s in steps if s.rule == "NS_B_Par"]
    assert (par[0].lhs, par[0].rhs) == ("sem_B(((X > 1)))", "sem_B((X > 1))")
    assert (par[1].lhs, par[1].rhs) == ("sem_B((X > 1))", "sem_B(X > 1)")


def test_extension_rules_are_marked() -> None:
    src = prog("X := 7 div 2")
    _, steps = build_term_with_steps(parse_program(src), src)
    div = [s for s in steps if s.rule == "NS_A_Div"][0]
    assert div.to_dict()["extension"] is True
    assert "NS_A_Add" not in EXTENSION_RULES and "NS_B_and" in EXTENSION_RULES


def test_pretty_layout(power_source: str) -> None:
    pretty = render_pretty(build_term(parse_program(power_source)), width=40)
    lines = pretty.splitlines()
    assert lines[0] == "AS^R(1̅)"
    assert lines[1].startswith("• WH(")
    one = build_term(parse_program(prog("X := 1")))
    assert render_pretty(one) == render_text(one)


def test_term_json(power_source: str) -> None:
    data = build_term(parse_program(power_source)).to_dict()
    assert data["kind"] == "COMP"
    assert data["args"][0]["kind"] == "AS" and data["args"][0]["var"] == "R"
    assert data["args"][1]["args"][0]["function"] == "gr"


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.stem)
def test_golden_terms(path: Path) -> None:
    source = path.read_text("utf-8")
    term = build_term(parse(source).ast)
    actual = (f"{render_text(term, 'unicode')}\n{render_text(term, 'ascii')}\n"
              f"{render_text(term, 'latex')}\n")
    golden = GOLDEN / f"{path.stem}.term.txt"
    if os.environ.get("UPDATE_GOLDEN") == "1" or not golden.exists():
        golden.write_text(actual, encoding="utf-8")
    assert actual == golden.read_text("utf-8")
