"""SEM-01: recursive construction of semantic terms, renderers, golden tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sipl.parser import parse, parse_program
from sipl.semantics import build_term, build_term_with_steps, render_pretty, render_text
from sipl.semantics.terms import AssignT, CompT, ConstT, DenameT, IdT, IfT, SuperT, WhileT

from .conftest import EXAMPLES

GOLDEN = Path(__file__).parent / "golden"
EXAMPLE_FILES = sorted(p for p in EXAMPLES.glob("*.sipl") if p.stem != "syntax_error")


def term_of(src: str, style: str = "ascii") -> str:
    return render_text(build_term(parse_program(src)), style)


@pytest.mark.parametrize("source, expected", [
    ("X := 1", "AS^X(#1)"),
    ("skip", "id"),
    ("X := Y", "AS^X(Y=>)"),
    ("X := 1; Y := 2", "AS^X(#1) o AS^Y(#2)"),
    ("begin X := 1 end", "AS^X(#1)"),
    ("X := A - B / 2", "AS^X(S^2(-, A=>, S^2(/, B=>, #2)))"),
    ("if X < 1 then skip else X := 0", "IF(S^2(<, X=>, #1), id, AS^X(#0))"),
    ("while not (X >= 1) do X := X + 1",
     "WH(S^1(not, S^2(>=, X=>, #1)), AS^X(S^2(+, X=>, #1)))"),
    ("if true and false or X <> 2 then skip else skip",
     "IF(S^2(or, S^2(and, #T, #F), S^2(<>, X=>, #2)), id, id)"),
])
def test_construction_rules(source: str, expected: str) -> None:
    assert term_of(source) == expected


def test_unicode_course_notation(power_source: str) -> None:
    text = term_of(power_source, "unicode")
    assert text == ("AS^R(1̅) • WH(S²(>, Y⇒, 0̅), AS^R(S²(×, R⇒, X⇒)) • "
                    "AS^Y(S²(−, Y⇒, 1̅)))")


def test_latex_rendering() -> None:
    text = term_of("if X <= 10 then X := X * 2 else skip", "latex")
    assert text == (r"\mathrm{IF}(S^{2}(\le, X\Rightarrow, \overline{10}), "
                    r"\mathrm{AS}^{X}(S^{2}(\cdot, X\Rightarrow, \overline{2})), \mathrm{id})")


def test_term_structure_and_links(power_source: str) -> None:
    prog = parse_program(power_source)
    term = build_term(prog)
    assert isinstance(term, CompT)
    first, loop = term.flatten()
    assert isinstance(first, AssignT) and isinstance(first.expr, ConstT)
    assert isinstance(loop, WhileT) and isinstance(loop.cond, SuperT)
    # every term node is linked to an AST node of the same construct
    nodes = prog.node_by_id()
    for t in term.walk():
        assert t.ast_id is not None
        kind = nodes[t.ast_id].kind
        expected = {"AS": "Assign", "COMP": "Seq", "WH": "While", "IF": "If", "ID": "Skip",
                    "CONST": "Num", "DEN": "Var", "BCONST": "BoolLit"}.get(t.kind)
        if expected:
            assert kind == expected
    ids = [t.id for t in term.walk()]
    assert ids == list(range(len(ids)))


def test_sorts() -> None:
    term = build_term(parse_program("if X > 1 then Y := X + 1 else skip"))
    assert isinstance(term, IfT)
    assert term.sort == "program"
    assert term.cond.sort == "predicate"
    assert isinstance(term.then, AssignT) and term.then.expr.sort == "function"
    assert isinstance(term.other, IdT)
    assert isinstance(build_term(parse_program("X := Y")).walk().__next__(), AssignT)
    assert isinstance(list(build_term(parse_program("X := Y")).walk())[1], DenameT)


def test_construction_steps_are_bottom_up(power_source: str) -> None:
    term, steps = build_term_with_steps(parse_program(power_source), power_source)
    rules = [s.rule for s in steps]
    assert rules[0] == "T-CONST"            # 1 in R := 1
    assert rules[1] == "T-AS"               # R := 1
    assert rules[-1] == "T-BLOCK"           # the outer begin ... end
    assert steps[-1].term is term
    assert steps[1].source == "R := 1"
    assert all(s.to_dict()["term"] for s in steps)


def test_pretty_layout(power_source: str) -> None:
    pretty = render_pretty(build_term(parse_program(power_source)), width=40)
    lines = pretty.splitlines()
    assert lines[0] == "AS^R(1̅)"
    assert lines[1].startswith("• WH(")
    flat = render_text(build_term(parse_program("X := 1")))
    assert render_pretty(build_term(parse_program("X := 1"))) == flat


def test_term_json(power_source: str) -> None:
    data = build_term(parse_program(power_source)).to_dict()
    assert data["kind"] == "COMP"
    assert data["args"][0]["kind"] == "AS" and data["args"][0]["var"] == "R"


# ------------------------------------------------------------------ golden

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
