"""VIS-01 / SEM-03: exporters and the HTML chain viewer are generated from real data."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from sipl.parser import parse
from sipl.semantics import build_term_with_steps, evaluate
from sipl.visualization import (
    build_payload,
    derivation_tree,
    from_ast,
    from_parse_tree,
    from_term,
    leaf_traversal,
    render_html,
    to_dot,
    to_json,
    to_svg,
    to_text,
    traversal_report,
)


@pytest.fixture
def parsed(power_source: str):  # type: ignore[no-untyped-def]
    return parse(power_source)


def test_text_tree_links_nodes_to_source(parsed) -> None:  # type: ignore[no-untyped-def]
    text = to_text(from_parse_tree(parsed.tree), parsed.source)
    lines = text.splitlines()
    assert lines[0].startswith("program")
    assert "1:1-8:4" in lines[0]
    assert any("assignment" in ln and "«R := 1»" in ln for ln in lines)
    assert any("IDENT X" in ln and "5:12-5:13" in ln for ln in lines)
    assert "└── " in text and "├── " in text


def test_course_derivation_tree_as_in_practical_work_1(parsed) -> None:  # type: ignore[no-untyped-def]
    tree = derivation_tree(parsed)
    assert tree.label == "<програма> P1"
    labels = [n.label.split(" ")[0] for n in tree.walk() if n.kind != "token"]
    assert set(labels) == {"<програма>", "<оператор>", "<вираз>", "<умова>", "<змінна>",
                           "<число>"}
    rules = {n.label.split(" ")[1] for n in tree.walk() if " " in n.label and n.kind != "token"}
    assert rules == {"P1", "S1", "S2", "S4", "S5", "A1", "A2", "A4", "A5", "B2"}
    # the 24 numbered leaves of the practicum figure
    assert leaf_traversal(tree) == ["begin", "R", ":=", "1", ";", "while", "Y", ">", "0", "do",
                                    "begin", "R", ":=", "R", "*", "X", ";", "Y", ":=", "Y",
                                    "-", "1", "end", "end"]
    report = traversal_report(tree, parsed)
    assert "1 begin 2 R 3 := 4 1 5 ;" in report and "24 end" in report
    assert "синтаксично правильна" in report


def test_derivation_tree_parentheses_and_negation() -> None:
    p = parse("begin X := ((1 + -2)); if ¬(X = 1) then skip else skip end")
    tree = derivation_tree(p)
    labels = [n.label for n in tree.walk() if n.kind != "token"]
    assert labels.count("<вираз> A6") == 2 and "<умова> B5" in labels
    assert "<умова> B4" in labels and "<оператор> S6" in labels
    assert leaf_traversal(tree) == [t.text for t in p.tokens if t.kind != "EOF"]
    ext = derivation_tree(parse("begin X := 7 div 2 end"))
    assert any("розш. div" in n.label for n in ext.walk())


def test_compact_tree_is_smaller(parsed) -> None:  # type: ignore[no-untyped-def]
    full = list(from_parse_tree(parsed.tree).walk())
    compact = list(from_parse_tree(parsed.tree, compact=True).walk())
    assert len(compact) < len(full)
    # leaves (tokens) are preserved
    assert sum(n.kind == "token" for n in full) == sum(n.kind == "token" for n in compact)


def test_json_tree(parsed) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(to_json(from_parse_tree(parsed.tree), parsed.source))
    assert data["label"] == "program"
    assert data["text"] == parsed.source
    assert data["span"]["start"]["line"] == 1


def test_dot_export(parsed) -> None:  # type: ignore[no-untyped-def]
    dot = to_dot(from_ast(parsed.ast), parsed.source, "AST")
    assert dot.startswith('digraph "AST"')
    assert "n0 -> n1;" in dot
    assert 'tooltip="Assign R := [2:2-2:8]: R := 1"' in dot
    if shutil.which("dot"):
        out = subprocess.run(["dot", "-Tsvg"], input=dot, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr


def test_svg_export(parsed) -> None:  # type: ignore[no-untyped-def]
    svg = to_svg(from_parse_tree(parsed.tree, compact=True), parsed.source, "tree")
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    nodes = re.findall(r'<g class="n" data-id="(\d+)" data-start="(\d+)" data-end="(\d+)"', svg)
    assert nodes
    for _, s, e in nodes:
        assert 0 <= int(s) <= int(e) <= len(parsed.source)
    assert "<title>" in svg


def test_term_tree_has_ast_links(parsed) -> None:  # type: ignore[no-untyped-def]
    term, _ = build_term_with_steps(parsed.ast, parsed.source)
    spans = {n.id: n.span for n in parsed.ast.walk()}
    v = from_term(term, spans)
    assert v.label == "•"
    assert all(n.span is not None for n in v.walk())


def test_html_payload_is_consistent(parsed) -> None:  # type: ignore[no-untyped-def]
    term, steps = build_term_with_steps(parsed.ast, parsed.source)
    result = evaluate(term, {"X": 2, "Y": 2})
    payload = build_payload(parsed, term, steps, result, {"X": 2, "Y": 2}, "power.sipl")
    ast_ids = {n.id for n in parsed.ast.walk()}
    # every term refers to an existing AST node, every AST statement has a term
    assert all(t["ast"] in ast_ids for t in payload["terms"].values())
    for n in parsed.ast.walk():
        if n.category == "stmt":
            assert str(n.id) in payload["astTerm"]
    # trace refers to existing terms
    assert all(str(e["term_id"]) in payload["terms"] for e in payload["eval"]["trace"])
    html = render_html(payload)
    assert html.startswith("<!DOCTYPE html>")
    assert "power.sipl" in html
    assert "</script>" in html and html.count("<script>") == 1
    m = re.search(r"const D = (\{.*?\});\n", html, re.S)
    assert m and json.loads(m.group(1).replace("<\\/", "</"))["eval"]["status"] == "defined"


def test_html_without_state(parsed) -> None:  # type: ignore[no-untyped-def]
    term, steps = build_term_with_steps(parsed.ast, parsed.source)
    html = render_html(build_payload(parsed, term, steps, None, None))
    assert '"eval": null' in html


def test_html_escapes_script_end() -> None:
    src = "begin X := 1 { </script><b> } end"
    p = parse(src)
    term, steps = build_term_with_steps(p.ast, src)
    html = render_html(build_payload(p, term, steps, None, None))
    assert html.count("</script>") == 1
