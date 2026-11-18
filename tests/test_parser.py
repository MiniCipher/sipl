"""CORE-02: lexer, parser, typed AST with SourceSpan, diagnostics."""

from __future__ import annotations

import pytest

from sipl import ast as A
from sipl.diagnostics import SiplSyntaxError
from sipl.lexer import tokenize
from sipl.parser import parse, parse_program, parse_tree

from .conftest import prog


def syntax_error(source: str) -> SiplSyntaxError:
    with pytest.raises(SiplSyntaxError) as info:
        parse(source)
    return info.value


# ------------------------------------------------------------------- lexer

def test_tokens_and_aliases() -> None:
    kinds = [t.kind for t in tokenize("X := 1 ÷ 2 ≤ 3 && ¬ y ≠ 4 div 5 || z ∨ w mod 2 % 3")]
    assert kinds == ["IDENT", ":=", "NUMBER", "/", "NUMBER", "<=", "NUMBER", "and", "not",
                     "IDENT", "<>", "NUMBER", "/", "NUMBER", "or", "IDENT", "or", "IDENT",
                     "mod", "NUMBER", "mod", "NUMBER", "EOF"]


def test_textbook_typography() -> None:
    # the textbook writes M–N (en dash) and R ∗ X (asterisk operator)
    kinds = [t.kind for t in tokenize("M:=M–N; R := R ∗ X − 1")]
    assert kinds == ["IDENT", ":=", "IDENT", "-", "IDENT", ";", "IDENT", ":=", "IDENT", "*",
                     "IDENT", "-", "NUMBER", "EOF"]


def test_token_positions() -> None:
    toks = tokenize("begin\n  Xy := 10\nend")
    xy = toks[1]
    assert (xy.text, xy.span.start.line, xy.span.start.column) == ("Xy", 2, 3)
    assert (xy.span.end.line, xy.span.end.column) == (2, 5)
    num = toks[3]
    assert num.span.start.offset == 14 and num.span.end.offset == 16


def test_comments_are_skipped() -> None:
    kinds = [t.kind for t in tokenize("// c\nX { multi\nline } := 1 // end")]
    assert kinds == ["IDENT", ":=", "NUMBER", "EOF"]


@pytest.mark.parametrize("source, code, col", [
    ("begin X := 1 @", "E004", 14),
    ("begin X : 1", "E003", 9),
    ("begin 2abc := 1", "E002", 7),
    ("begin X := 1 { open", "E001", 14),
])
def test_lexical_errors(source: str, code: str, col: int) -> None:
    err = syntax_error(source)
    assert err.diagnostic.code == code
    assert err.diagnostic.column == col


# -------------------------------------------------------------------- AST

def test_power_ast(power_source: str) -> None:
    prog = parse_program(power_source)
    assert isinstance(prog, A.Program)
    seq = prog.body  # P ::= begin S end - the program's begin/end is not a Block
    assert isinstance(seq, A.Seq)
    assert isinstance(seq.first, A.Assign) and seq.first.target == "R"
    loop = seq.second
    assert isinstance(loop, A.While)
    assert isinstance(loop.cond, A.Compare) and loop.cond.op == ">"
    assert prog.variables() == ["R", "Y", "X"]


def test_ids_are_preorder_and_unique(power_source: str) -> None:
    prog = parse_program(power_source)
    ids = [n.id for n in prog.walk()]
    assert ids == list(range(len(ids)))
    assert prog.node_by_id()[0] is prog


def test_spans_point_to_source(power_source: str) -> None:
    prog = parse_program(power_source)
    for node in prog.walk():
        text = node.span.text(power_source)
        assert text == text.strip(), node.kind
        if isinstance(node, A.Assign):
            assert text.startswith(node.target) and ":=" in text
            assert node.target_span.text(power_source) == node.target
        if isinstance(node, A.While):
            assert text.startswith("while") and text.endswith("end")
        if isinstance(node, A.Var):
            assert text == node.name
    assert prog.span.start.line == 1 and prog.span.end.line == 8
    assert prog.body.span.start.line == 2 and prog.body.span.end.line == 7


def test_parenthesised_expression_span_includes_parens() -> None:
    src = prog("X := ((1 + 2)) * 3")
    assign = parse_program(src).body
    assert isinstance(assign, A.Assign)
    mul = assign.value
    assert isinstance(mul, A.BinOp) and mul.op == "*"
    assert mul.left.span.text(src) == "((1 + 2))"
    assert mul.left.inner_span.text(src) == "1 + 2"
    assert [s.text(src) for s in mul.left.paren_spans] == ["(1 + 2)", "((1 + 2))"]
    assert mul.left.to_dict()["parens"] == 2


def test_negative_numbers() -> None:
    assign = parse_program(prog("X := -1 - -2")).body
    assert isinstance(assign, A.Assign)
    assert assign.to_sexpr() == "(assign X (- (num -1) (num -2)))"
    assert assign.value.children()[0].span.length == 2


def test_textbook_gcd_program() -> None:
    src = "begin\n while ¬M=N do\n  if M>N then M:=M–N else N:=N–M\nend"
    assert parse_program(src, strict=True).to_sexpr() == (
        "(while (not (= (var M) (var N))) (if (> (var M) (var N)) (assign M (- (var M) "
        "(var N))) (assign N (- (var N) (var M)))))")


def test_strict_mode_and_extension_warnings() -> None:
    src = prog("if X >= 1 and true then X := X mod 2 else skip")
    res = parse(src)
    assert [w.code for w in res.warnings] == ["W201"] * 4
    assert "gre" in res.warnings[0].message
    with pytest.raises(SiplSyntaxError) as info:
        parse(src, strict=True)
    assert info.value.diagnostic.code == "E201"
    assert info.value.diagnostic.column == 12
    assert not parse(prog("if ¬(X = 1) ∨ X > 2 then skip else skip"), strict=True).warnings


@pytest.mark.parametrize("source, sexpr", [
    ("X := 1 + 2 * 3", "(assign X (+ (num 1) (* (num 2) (num 3))))"),
    ("X := 8 - 4 - 2", "(assign X (- (- (num 8) (num 4)) (num 2)))"),
    ("X := 8 / 4 / 2", "(assign X (/ (/ (num 8) (num 4)) (num 2)))"),
    ("X := 8 mod 3 * 2", "(assign X (* (mod (num 8) (num 3)) (num 2)))"),
    ("if not X = 1 or X > 2 then skip else skip",
     "(if (or (not (= (var X) (num 1))) (> (var X) (num 2))) (skip) (skip))"),
    ("A := 1; B := 2; C := 3",
     "(seq (seq (assign A (num 1)) (assign B (num 2))) (assign C (num 3)))"),
    ("if true or false and not false then skip else skip",
     "(if (or (true) (and (false) (not (false)))) (skip) (skip))"),
    ("while (X) < 3 do skip", "(while (< (var X) (num 3)) (skip))"),
    ("while (X < 3) do skip", "(while (< (var X) (num 3)) (skip))"),
    ("while ((X + 1) * 2 > Y) and true do skip",
     "(while (and (> (* (+ (var X) (num 1)) (num 2)) (var Y)) (true)) (skip))"),
    ("if X = 1 then if Y = 2 then A := 1 else A := 2 else A := 3",
     "(if (= (var X) (num 1)) (if (= (var Y) (num 2)) (assign A (num 1)) (assign A (num 2)))"
     " (assign A (num 3)))"),
])
def test_ast_shapes(source: str, sexpr: str) -> None:
    assert parse_program(prog(source)).to_sexpr() == sexpr


def test_if_branch_is_single_statement() -> None:
    # `;` after the else-branch belongs to the outer sequence
    program = parse_program(prog("if X > 0 then Y := 1 else Y := 2; Z := 3"))
    assert isinstance(program.body, A.Seq)
    assert isinstance(program.body.first, A.If)


def test_ast_json_roundtrip_fields(power_source: str) -> None:
    data = parse_program(power_source).to_dict()
    assert data["type"] == "Program"
    assert data["body"]["type"] == "Seq"
    assert data["span"]["start"] == {"offset": 0, "line": 1, "column": 1}
    without = parse_program(power_source).to_dict(with_spans=False)
    assert "span" not in without


def test_parse_tree_labels_follow_grammar() -> None:
    tree, _ = parse_tree("begin X := 1 end")
    labels = [n.label for n in tree.walk()]
    assert labels[:5] == ["program", "begin", "stmt_seq", "statement", "assignment"]
    leaves = [n.token.text for n in tree.walk() if n.token is not None]
    assert leaves == ["begin", "X", ":=", "1", "end"]
    compact = tree.compact()
    assert compact.children[1].label == "stmt_seq›statement›assignment"


# ------------------------------------------------------------- diagnostics

@pytest.mark.parametrize("source, code, line, col, needle", [
    ("begin\n X := 1;\nend", "E104", 2, 8, "';'"),
    ("begin X = 1 end", "E106", 1, 9, "':='"),
    ("begin if X > 1 then skip end", "E108", 1, 26, "else"),
    ("begin if X > 1 then skip; else skip end", "E107", 1, 25, "else"),
    ("begin X := 1", "E110", 1, 13, "begin"),
    ("begin X := 1 end end", "E103", 1, 18, "end"),
    ("begin X := 1\nY := 2 end", "E102", 2, 1, "';'"),
    ("", "E101", 1, 1, "порожня"),
    ("begin end", "E109", 1, 7, "begin"),
    ("begin X := true end", "E111", 1, 12, "арифметичний"),
    ("begin while X do skip end", "E112", 1, 15, "порівняння"),
    ("begin ; X := 1 end", "E105", 1, 7, "оператор"),
    ("X := 1", "E113", 1, 1, "begin"),
    ("begin skip end; X := 1", "E114", 1, 15, "після 'end'"),
    ("begin X := -Y end", "E111", 1, 12, "арифметичний"),
])
def test_diagnostics(source: str, code: str, line: int, col: int, needle: str) -> None:
    d = syntax_error(source).diagnostic
    assert (d.code, d.line, d.column) == (code, line, col)
    assert needle in d.message
    rendered = d.render(source, "t.sipl")
    assert rendered.startswith(f"t.sipl:{line}:{col}:")
    assert "^" in rendered
    assert d.to_dict()["line"] == line


def test_backtracking_reports_furthest_error() -> None:
    d = syntax_error("begin while (X + 1 do skip end").diagnostic
    assert d.column == 20  # at 'do', not at the opening parenthesis
