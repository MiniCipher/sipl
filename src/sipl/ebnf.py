"""Loader and generic recognizer for the machine-readable grammar (CORE-01).

Reads ``sipl.ebnf`` (ISO-EBNF subset: ``=``, ``,``, ``|``, ``{}``, ``[]``, ``()``,
quoted terminals, ``(* comments *)``) and decides membership of a token
sequence in the language by an exhaustive set-based recognizer (it explores
*all* alternatives, so it is exact for any non-left-recursive grammar).

This is independent from the hand-written parser and is used by the tests to
check that the parser accepts exactly the language defined by the grammar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from .lexer import EOF, Token, tokenize


@dataclass(frozen=True)
class Terminal:
    kind: str


@dataclass(frozen=True)
class NonTerminal:
    name: str


@dataclass(frozen=True)
class Seq:
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class Alt:
    options: tuple[Expr, ...]


@dataclass(frozen=True)
class Repeat:  # { x }
    body: Expr


@dataclass(frozen=True)
class Optional_:  # [ x ]
    body: Expr


Expr = Terminal | NonTerminal | Seq | Alt | Repeat | Optional_

_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<comment>\(\*.*?\*\))
      | (?P<string>"[^"]*"|'[^']*')
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<sym>[=,|;{}\[\]()])
    )""",
    re.VERBOSE | re.DOTALL,
)


class GrammarError(Exception):
    pass


def _lex_ebnf(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise GrammarError(f"bad EBNF near: {text[pos:pos + 20]!r}")
        pos = m.end()
        if m.group("comment"):
            continue
        if m.group("string"):
            out.append(("str", m.group("string")[1:-1]))
        elif m.group("name"):
            out.append(("name", m.group("name")))
        else:
            out.append(("sym", m.group("sym")))
    return out


@dataclass
class Grammar:
    rules: dict[str, Expr]
    start: str
    order: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------- parsing
    @classmethod
    def from_text(cls, text: str) -> Grammar:
        toks = _lex_ebnf(text)
        i = 0

        def peek() -> tuple[str, str] | None:
            return toks[i] if i < len(toks) else None

        def take(sym: str) -> None:
            nonlocal i
            if peek() != ("sym", sym):
                raise GrammarError(f"expected {sym!r}, got {peek()!r}")
            i += 1

        def alt() -> Expr:
            options = [seq()]
            while peek() == ("sym", "|"):
                take("|")
                options.append(seq())
            return options[0] if len(options) == 1 else Alt(tuple(options))

        def seq() -> Expr:
            items = [primary()]
            while peek() == ("sym", ","):
                take(",")
                items.append(primary())
            return items[0] if len(items) == 1 else Seq(tuple(items))

        def primary() -> Expr:
            nonlocal i
            tok = peek()
            if tok is None:
                raise GrammarError("unexpected end of grammar")
            kind, val = tok
            i += 1
            if kind == "str":
                return Terminal(val)
            if kind == "name":
                return NonTerminal(val)
            closing = {"{": "}", "[": "]", "(": ")"}.get(val)
            if closing is None:
                raise GrammarError(f"unexpected {val!r}")
            body = alt()
            take(closing)
            if val == "{":
                return Repeat(body)
            if val == "[":
                return Optional_(body)
            return body

        rules: dict[str, Expr] = {}
        order: list[str] = []
        while peek() is not None:
            tok = peek()
            if tok is None or tok[0] != "name":
                raise GrammarError(f"rule name expected, got {tok!r}")
            name = tok[1]
            i += 1
            take("=")
            rules[name] = alt()
            take(";")
            order.append(name)
        if not order:
            raise GrammarError("empty grammar")
        g = cls(rules, order[0], order)
        g._validate()
        return g

    @classmethod
    def load(cls, path: str | Path | None = None, extended: bool = False) -> Grammar:
        """Load a grammar file; by default the packaged core grammar of the course
        (``extended=True``: the packaged ``sipl-ext.ebnf``)."""
        if path is None:
            name = "sipl-ext.ebnf" if extended else "sipl.ebnf"
            text = resources.files("sipl").joinpath(f"data/{name}").read_text("utf-8")
        else:
            text = Path(path).read_text("utf-8")
        return cls.from_text(text)

    def _validate(self) -> None:
        for name in self.undefined_nonterminals():
            if not name.isupper():
                raise GrammarError(f"undefined rule: {name}")

    def _walk(self, e: Expr) -> list[Expr]:
        out: list[Expr] = [e]
        if isinstance(e, Seq):
            for x in e.items:
                out += self._walk(x)
        elif isinstance(e, Alt):
            for x in e.options:
                out += self._walk(x)
        elif isinstance(e, (Repeat, Optional_)):
            out += self._walk(e.body)
        return out

    def undefined_nonterminals(self) -> set[str]:
        used = {x.name for r in self.rules.values() for x in self._walk(r)
                if isinstance(x, NonTerminal)}
        return used - set(self.rules)

    def terminals(self) -> set[str]:
        return {x.kind for r in self.rules.values() for x in self._walk(r)
                if isinstance(x, Terminal)}

    def token_classes(self) -> set[str]:
        """Upper-case names without a rule: IDENT, NUMBER (provided by the lexer)."""
        return self.undefined_nonterminals()

    # ------------------------------------------------------------- recognizer
    def accepts_tokens(self, tokens: list[Token]) -> bool:
        return self.recognize(tokens)[0]

    def recognize(self, tokens: list[Token]) -> tuple[bool, int]:
        """Return (accepted, furthest token index reached)."""
        toks = [t for t in tokens if t.kind != EOF]
        n = len(toks)
        memo: dict[tuple[str, int], frozenset[int]] = {}
        furthest = 0
        classes = self.token_classes()

        def match(e: Expr, pos: int) -> frozenset[int]:
            nonlocal furthest
            if isinstance(e, Terminal) or (isinstance(e, NonTerminal) and e.name in classes):
                kind = e.kind if isinstance(e, Terminal) else e.name
                if pos < n and toks[pos].kind == kind:
                    furthest = max(furthest, pos + 1)
                    return frozenset({pos + 1})
                return frozenset()
            if isinstance(e, NonTerminal):
                key = (e.name, pos)
                if key not in memo:
                    memo[key] = frozenset()  # guards against (unsupported) left recursion
                    memo[key] = match(self.rules[e.name], pos)
                return memo[key]
            if isinstance(e, Seq):
                current = frozenset({pos})
                for item in e.items:
                    nxt: set[int] = set()
                    for p in current:
                        nxt |= match(item, p)
                    current = frozenset(nxt)
                    if not current:
                        break
                return current
            if isinstance(e, Alt):
                res: set[int] = set()
                for opt in e.options:
                    res |= match(opt, pos)
                return frozenset(res)
            if isinstance(e, Optional_):
                return frozenset({pos}) | match(e.body, pos)
            if isinstance(e, Repeat):
                result = {pos}
                frontier = {pos}
                while frontier:
                    new: set[int] = set()
                    for p in frontier:
                        new |= match(e.body, p)
                    frontier = new - result
                    result |= new
                return frozenset(result)
            raise TypeError(e)

        ends = match(NonTerminal(self.start), 0)
        return n in ends, furthest

    def accepts(self, source: str) -> bool:
        """True iff ``source`` is lexically valid and derivable from the start rule."""
        try:
            tokens = tokenize(source)
        except Exception:
            return False
        return self.accepts_tokens(tokens)
