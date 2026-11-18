"""Semantic terms of SIPL in the notation of the course (SEM-01).

The semantics is compositional (М.С. Нікітченко): a program denotes a
function on states built from basic functions by compositions:

=====================  ==================================================
``AS^x(A)``            assignment composition (присвоювання)
``P1 • P2``            sequential composition: first P1, then P2
``IF(B, P1, P2)``      branching composition
``WH(B, P)``           cycle composition
``id``                 identity function (skip)
``x⇒``                 denaming function (розіменування)
``n̄``                  constant function n̄(st) = n
``S²(f, A1, A2)``      superposition of a binary function (add, sub, mult, eq, gr, or, ...)
``S¹(neg, B)``         superposition of the unary function neg
=====================  ==================================================
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(eq=False, kw_only=True)
class Term:
    id: int = -1
    ast_id: int | None = None

    kind: ClassVar[str] = "term"
    #: sort of the denoted function: program (state -> state),
    #: function (state -> int) or predicate (state -> bool)
    sort: ClassVar[str] = "program"

    def children(self) -> list[Term]:
        return []

    def walk(self) -> Iterator[Term]:
        yield self
        for c in self.children():
            yield from c.walk()

    def attrs(self) -> dict[str, Any]:
        return {}

    def to_dict(self) -> dict[str, Any]:
        from .render import render_text

        data: dict[str, Any] = {"kind": self.kind, "id": self.id, "ast_id": self.ast_id,
                                "sort": self.sort}
        data.update(self.attrs())
        data["text"] = render_text(self, "unicode")
        kids = self.children()
        if kids:
            data["args"] = [c.to_dict() for c in kids]
        return data


@dataclass(eq=False, kw_only=True)
class AssignT(Term):
    var: str
    expr: Term
    kind: ClassVar[str] = "AS"

    def children(self) -> list[Term]:
        return [self.expr]

    def attrs(self) -> dict[str, Any]:
        return {"var": self.var}


@dataclass(eq=False, kw_only=True)
class CompT(Term):
    first: Term
    second: Term
    kind: ClassVar[str] = "COMP"

    def children(self) -> list[Term]:
        return [self.first, self.second]

    def flatten(self) -> list[Term]:
        """Components of an associative chain P1 • P2 • ... • Pn."""
        out: list[Term] = []
        for part in (self.first, self.second):
            if isinstance(part, CompT):
                out.extend(part.flatten())
            else:
                out.append(part)
        return out


@dataclass(eq=False, kw_only=True)
class IfT(Term):
    cond: Term
    then: Term
    other: Term
    kind: ClassVar[str] = "IF"

    def children(self) -> list[Term]:
        return [self.cond, self.then, self.other]


@dataclass(eq=False, kw_only=True)
class WhileT(Term):
    cond: Term
    body: Term
    kind: ClassVar[str] = "WH"

    def children(self) -> list[Term]:
        return [self.cond, self.body]


@dataclass(eq=False, kw_only=True)
class IdT(Term):
    kind: ClassVar[str] = "ID"


@dataclass(eq=False, kw_only=True)
class ConstT(Term):
    value: int
    kind: ClassVar[str] = "CONST"
    sort: ClassVar[str] = "function"

    def attrs(self) -> dict[str, Any]:
        return {"value": self.value}


@dataclass(eq=False, kw_only=True)
class BoolConstT(Term):
    value: bool
    kind: ClassVar[str] = "BCONST"
    sort: ClassVar[str] = "predicate"

    def attrs(self) -> dict[str, Any]:
        return {"value": self.value}


@dataclass(eq=False, kw_only=True)
class DenameT(Term):
    var: str
    kind: ClassVar[str] = "DEN"
    sort: ClassVar[str] = "function"

    def attrs(self) -> dict[str, Any]:
        return {"var": self.var}


#: canonical operator -> name of the basic function of the algebra A_SIPL
#: (textbook, section 1.3.1: add, sub, mult, eq, gr, or, neg; the practicum also
#: uses gre, less, div, mod; leq, neq, and are named in the same style)
OP_NAMES = {
    "+": "add", "-": "sub", "*": "mult", "/": "div", "mod": "mod",
    "=": "eq", ">": "gr", "<": "less", "<=": "leq", "<>": "neq", ">=": "gre",
    "or": "or", "and": "and", "not": "neg",
}
CORE_OPS = frozenset({"+", "-", "*", "=", ">", "or", "not"})
ARITH = {"+", "-", "*", "/", "mod"}
RELATIONS = {"<", "<=", "=", "<>", ">", ">="}
LOGIC = {"and", "or", "not"}


@dataclass(eq=False, kw_only=True)
class SuperT(Term):
    op: str
    args: list[Term] = field(default_factory=list)
    kind: ClassVar[str] = "S"

    @property
    def sort(self) -> str:  # type: ignore[override]
        return "function" if self.op in ARITH else "predicate"

    @property
    def name(self) -> str:
        """Name of the basic function: add, sub, mult, eq, gr, or, neg, ..."""
        return OP_NAMES[self.op]

    def children(self) -> list[Term]:
        return list(self.args)

    def attrs(self) -> dict[str, Any]:
        return {"op": self.op, "function": OP_NAMES[self.op], "arity": len(self.args)}


def assign_ids(root: Term) -> None:
    for i, t in enumerate(root.walk()):
        t.id = i
