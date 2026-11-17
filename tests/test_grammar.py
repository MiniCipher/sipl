"""CORE-01: the machine-readable grammar, its corpus and agreement with the parser."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from sipl.diagnostics import SiplSyntaxError
from sipl.ebnf import Alt, Grammar, GrammarError, NonTerminal, Optional_, Repeat, Seq, Terminal
from sipl.parser import parse

from .conftest import CONFORMANCE, GRAMMAR

VALID = sorted((GRAMMAR / "examples" / "valid").glob("*.sipl"))
INVALID = sorted((GRAMMAR / "examples" / "invalid").glob("*.sipl"))


@pytest.fixture(scope="module")
def grammar() -> Grammar:
    return Grammar.load(GRAMMAR / "sipl.ebnf")


def parser_accepts(source: str) -> bool:
    try:
        parse(source)
    except SiplSyntaxError:
        return False
    return True


def test_corpus_size() -> None:
    assert len(VALID) >= 10
    assert len(INVALID) >= 10


def test_packaged_grammar_is_identical() -> None:
    packaged = Path(__file__).resolve().parents[1] / "src" / "sipl" / "data" / "sipl.ebnf"
    assert packaged.read_text("utf-8") == (GRAMMAR / "sipl.ebnf").read_text("utf-8")
    assert Grammar.load().rules == Grammar.load(GRAMMAR / "sipl.ebnf").rules


def test_grammar_structure(grammar: Grammar) -> None:
    assert grammar.start == "program"
    assert grammar.token_classes() == {"IDENT", "NUMBER"}
    expected_rules = {"program", "stmt_seq", "statement", "assignment", "if_stmt", "while_stmt",
                      "block", "skip_stmt", "aexpr", "term", "factor", "bexpr", "bterm",
                      "bfactor", "comparison", "relop", "addop", "mulop"}
    assert set(grammar.rules) == expected_rules
    # all course constructs are present as terminals
    for kw in ["if", "then", "else", "while", "do", "begin", "end", "skip", ":=", ";",
               "true", "false", "and", "or", "not", "+", "-", "*", "/"]:
        assert kw in grammar.terminals()


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_programs(grammar: Grammar, path: Path) -> None:
    source = path.read_text("utf-8")
    assert grammar.accepts(source), "grammar must accept"
    assert parser_accepts(source), "parser must accept"


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_programs(grammar: Grammar, path: Path) -> None:
    source = path.read_text("utf-8")
    assert not grammar.accepts(source), "grammar must reject"
    assert not parser_accepts(source), "parser must reject"


def test_parser_agrees_with_grammar_on_conformance_cases(grammar: Grammar) -> None:
    for sipl in sorted((CONFORMANCE / "cases").glob("*.sipl")):
        source = sipl.read_text("utf-8")
        expect = json.loads(sipl.with_name(sipl.stem + ".expect.json").read_text("utf-8"))
        should = expect["syntax"] == "ok"
        assert grammar.accepts(source) == should, sipl.name
        assert parser_accepts(source) == should, sipl.name


# ----------------------------------------------------------- random programs

def _generate(grammar: Grammar, rng: random.Random, depth: int = 0) -> list[str]:
    lexemes = {"IDENT": ["X", "Y", "Res", "i1"], "NUMBER": ["0", "1", "42"]}

    def gen(e: object, d: int) -> list[str]:
        if isinstance(e, Terminal):
            return [e.kind]
        if isinstance(e, NonTerminal):
            if e.name in lexemes:
                return [rng.choice(lexemes[e.name])]
            return gen(grammar.rules[e.name], d + 1)
        if isinstance(e, Seq):
            return [t for item in e.items for t in gen(item, d)]
        if isinstance(e, Alt):
            if d < 9:
                return gen(rng.choice(e.options), d)
            # deep in the tree: take a terminal option, otherwise the last (simplest) one
            for opt in e.options:
                if isinstance(opt, Terminal) or (isinstance(opt, NonTerminal)
                                                 and opt.name in lexemes):
                    return gen(opt, d)
            return gen(e.options[-1], d)
        if isinstance(e, Repeat):
            n = rng.randint(0, 2) if d < 8 else 0
            return [t for _ in range(n) for t in gen(e.body, d)]
        if isinstance(e, Optional_):
            return gen(e.body, d) if rng.random() < 0.5 else []
        raise TypeError(e)

    return gen(NonTerminal(grammar.start), depth)


def test_random_sentences_of_grammar_are_parsed(grammar: Grammar) -> None:
    rng = random.Random(2026)
    checked = 0
    for _ in range(300):
        words = _generate(grammar, rng)
        if len(words) > 200:
            continue
        source = " ".join(words)
        assert grammar.accepts(source), source
        result = parse(source)  # must not raise
        # pretty-printing back from the AST is not required, but the AST must cover all text
        assert result.ast.span.start.offset == 0
        checked += 1
    assert checked > 100


def test_ebnf_loader_errors() -> None:
    with pytest.raises(GrammarError):
        Grammar.from_text("a = b ;")  # undefined lower-case rule
    with pytest.raises(GrammarError):
        Grammar.from_text("a = 'x' ")  # missing ';'
    with pytest.raises(GrammarError):
        Grammar.from_text("")
    g = Grammar.from_text("s = 'a' , [ 'b' ] , { 'c' } ;")
    assert g.accepts("a") is False  # 'a' is an identifier token, not the terminal "a"


def test_ebnf_optional_and_repeat() -> None:
    g = Grammar.from_text("s = 'begin' , [ 'skip' ] , { ';' , 'skip' } , 'end' ;")
    assert g.accepts("begin end")
    assert g.accepts("begin skip ; skip ; skip end")
    assert not g.accepts("begin ; end end")
