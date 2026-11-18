"""Typed abstract syntax tree of SIPL (CORE-02).

Every node has a stable numeric ``id`` (pre-order index) and a ``span`` pointing
into the source. ``to_dict`` gives the JSON form, ``to_sexpr`` gives the
implementation-independent canonical form used by the conformance suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .span import SourceSpan

ARITH_OPS = ("+", "-", "*", "/", "mod")
REL_OPS = ("<", "<=", "=", "<>", ">", ">=")
LOGIC_OPS = ("and", "or")


@dataclass(eq=False, kw_only=True)
class Node:
    span: SourceSpan
    id: int = field(default=-1, compare=False)
    #: spans of enclosing parentheses, innermost first (rules A6 / B5: (a), (b));
    #: when non-empty, ``span`` is the outermost one and ``core_span`` excludes them
    paren_spans: list[SourceSpan] = field(default_factory=list, compare=False)
    core_span: SourceSpan | None = field(default=None, compare=False)

    @property
    def inner_span(self) -> SourceSpan:
        """Span of the construct itself, without enclosing parentheses."""
        return self.core_span or self.span

    kind: ClassVar[str] = "node"
    category: ClassVar[str] = "node"

    def children(self) -> list[Node]:
        return []

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children():
            yield from child.walk()

    def fields(self) -> dict[str, Any]:
        """Non-child attributes shown in JSON."""
        return {}

    def child_fields(self) -> dict[str, Node]:
        return {}

    def to_dict(self, with_spans: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.kind, "id": self.id}
        if with_spans:
            data["span"] = self.span.to_dict()
            if self.paren_spans:
                data["parens"] = len(self.paren_spans)
        data.update(self.fields())
        for name, child in self.child_fields().items():
            data[name] = child.to_dict(with_spans)
        return data

    def to_sexpr(self) -> str:
        raise NotImplementedError

    def label(self) -> str:
        """Short label for tree views."""
        extra = " ".join(str(v) for v in self.fields().values())
        return f"{self.kind} {extra}".strip()


# ---------------------------------------------------------------- expressions

@dataclass(eq=False, kw_only=True)
class AExpr(Node):
    category: ClassVar[str] = "aexpr"


@dataclass(eq=False, kw_only=True)
class Num(AExpr):
    value: int
    kind: ClassVar[str] = "Num"

    def fields(self) -> dict[str, Any]:
        return {"value": self.value}

    def to_sexpr(self) -> str:
        return f"(num {self.value})"


@dataclass(eq=False, kw_only=True)
class Var(AExpr):
    name: str
    kind: ClassVar[str] = "Var"

    def fields(self) -> dict[str, Any]:
        return {"name": self.name}

    def to_sexpr(self) -> str:
        return f"(var {self.name})"


@dataclass(eq=False, kw_only=True)
class BinOp(AExpr):
    op: str
    left: AExpr
    right: AExpr
    kind: ClassVar[str] = "BinOp"

    def children(self) -> list[Node]:
        return [self.left, self.right]

    def fields(self) -> dict[str, Any]:
        return {"op": self.op}

    def child_fields(self) -> dict[str, Node]:
        return {"left": self.left, "right": self.right}

    def to_sexpr(self) -> str:
        return f"({self.op} {self.left.to_sexpr()} {self.right.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class BExpr(Node):
    category: ClassVar[str] = "bexpr"


@dataclass(eq=False, kw_only=True)
class BoolLit(BExpr):
    value: bool
    kind: ClassVar[str] = "BoolLit"

    def fields(self) -> dict[str, Any]:
        return {"value": self.value}

    def to_sexpr(self) -> str:
        return "(true)" if self.value else "(false)"


@dataclass(eq=False, kw_only=True)
class Compare(BExpr):
    op: str
    left: AExpr
    right: AExpr
    kind: ClassVar[str] = "Compare"

    def children(self) -> list[Node]:
        return [self.left, self.right]

    def fields(self) -> dict[str, Any]:
        return {"op": self.op}

    def child_fields(self) -> dict[str, Node]:
        return {"left": self.left, "right": self.right}

    def to_sexpr(self) -> str:
        return f"({self.op} {self.left.to_sexpr()} {self.right.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class Not(BExpr):
    operand: BExpr
    kind: ClassVar[str] = "Not"

    def children(self) -> list[Node]:
        return [self.operand]

    def child_fields(self) -> dict[str, Node]:
        return {"operand": self.operand}

    def to_sexpr(self) -> str:
        return f"(not {self.operand.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class Logic(BExpr):
    op: str  # "and" | "or"
    left: BExpr
    right: BExpr
    kind: ClassVar[str] = "Logic"

    def children(self) -> list[Node]:
        return [self.left, self.right]

    def fields(self) -> dict[str, Any]:
        return {"op": self.op}

    def child_fields(self) -> dict[str, Node]:
        return {"left": self.left, "right": self.right}

    def to_sexpr(self) -> str:
        return f"({self.op} {self.left.to_sexpr()} {self.right.to_sexpr()})"


# ----------------------------------------------------------------- statements

@dataclass(eq=False, kw_only=True)
class Stmt(Node):
    category: ClassVar[str] = "stmt"


@dataclass(eq=False, kw_only=True)
class Assign(Stmt):
    target: str
    target_span: SourceSpan
    value: AExpr
    kind: ClassVar[str] = "Assign"

    def children(self) -> list[Node]:
        return [self.value]

    def fields(self) -> dict[str, Any]:
        return {"target": self.target}

    def child_fields(self) -> dict[str, Node]:
        return {"value": self.value}

    def to_sexpr(self) -> str:
        return f"(assign {self.target} {self.value.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class Seq(Stmt):
    first: Stmt
    second: Stmt
    kind: ClassVar[str] = "Seq"

    def children(self) -> list[Node]:
        return [self.first, self.second]

    def child_fields(self) -> dict[str, Node]:
        return {"first": self.first, "second": self.second}

    def to_sexpr(self) -> str:
        return f"(seq {self.first.to_sexpr()} {self.second.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class If(Stmt):
    cond: BExpr
    then_branch: Stmt
    else_branch: Stmt
    kind: ClassVar[str] = "If"

    def children(self) -> list[Node]:
        return [self.cond, self.then_branch, self.else_branch]

    def child_fields(self) -> dict[str, Node]:
        return {"cond": self.cond, "then": self.then_branch, "else": self.else_branch}

    def to_sexpr(self) -> str:
        return (f"(if {self.cond.to_sexpr()} {self.then_branch.to_sexpr()} "
                f"{self.else_branch.to_sexpr()})")


@dataclass(eq=False, kw_only=True)
class While(Stmt):
    cond: BExpr
    body: Stmt
    kind: ClassVar[str] = "While"

    def children(self) -> list[Node]:
        return [self.cond, self.body]

    def child_fields(self) -> dict[str, Node]:
        return {"cond": self.cond, "body": self.body}

    def to_sexpr(self) -> str:
        return f"(while {self.cond.to_sexpr()} {self.body.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class Block(Stmt):
    body: Stmt
    kind: ClassVar[str] = "Block"

    def children(self) -> list[Node]:
        return [self.body]

    def child_fields(self) -> dict[str, Node]:
        return {"body": self.body}

    def to_sexpr(self) -> str:
        return f"(block {self.body.to_sexpr()})"


@dataclass(eq=False, kw_only=True)
class Skip(Stmt):
    kind: ClassVar[str] = "Skip"

    def to_sexpr(self) -> str:
        return "(skip)"


@dataclass(eq=False, kw_only=True)
class Program(Node):
    body: Stmt
    kind: ClassVar[str] = "Program"
    category: ClassVar[str] = "program"

    def children(self) -> list[Node]:
        return [self.body]

    def child_fields(self) -> dict[str, Node]:
        return {"body": self.body}

    def to_sexpr(self) -> str:
        return self.body.to_sexpr()

    def variables(self) -> list[str]:
        """All variable names occurring in the program, in order of appearance."""
        seen: dict[str, None] = {}
        for node in self.walk():
            if isinstance(node, Assign):
                seen.setdefault(node.target)
            elif isinstance(node, Var):
                seen.setdefault(node.name)
        return list(seen)

    def node_by_id(self) -> dict[int, Node]:
        return {n.id: n for n in self.walk()}


def assign_ids(root: Node) -> None:
    for i, node in enumerate(root.walk()):
        node.id = i
