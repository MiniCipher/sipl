"""A uniform tree model used by all exporters (text, JSON, DOT, SVG, HTML)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .. import ast as A
from ..cst import ParseNode
from ..semantics.render import render_text
from ..semantics.terms import Term
from ..span import SourceSpan


@dataclass
class VNode:
    id: int
    label: str
    kind: str  # "rule" | "token" | "stmt" | "aexpr" | "bexpr" | "program" | "term"
    span: SourceSpan | None
    children: list[VNode] = field(default_factory=list)
    detail: str = ""
    ast_id: int | None = None

    def walk(self) -> Iterator[VNode]:
        yield self
        for c in self.children:
            yield from c.walk()

    def to_dict(self, source: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "label": self.label, "kind": self.kind}
        if self.span is not None:
            data["span"] = self.span.to_dict()
            if source is not None:
                data["text"] = self.span.text(source)
        if self.detail:
            data["detail"] = self.detail
        if self.ast_id is not None:
            data["ast_id"] = self.ast_id
        if self.children:
            data["children"] = [c.to_dict(source) for c in self.children]
        return data


def from_parse_tree(node: ParseNode, compact: bool = False) -> VNode:
    root = node.compact() if compact else node

    def conv(n: ParseNode) -> VNode:
        return VNode(n.id, n.display_label(), "token" if n.is_leaf else "rule", n.span,
                     [conv(c) for c in n.children])

    return conv(root)


_AST_LABELS = {
    "Assign": lambda n: f"Assign {n.target} :=",
    "BinOp": lambda n: f"BinOp {n.op}",
    "Compare": lambda n: f"Compare {n.op}",
    "Logic": lambda n: f"Logic {n.op}",
    "Num": lambda n: f"Num {n.value}",
    "Var": lambda n: f"Var {n.name}",
    "BoolLit": lambda n: f"Bool {'true' if n.value else 'false'}",
}


def from_ast(node: A.Node) -> VNode:
    label_fn = _AST_LABELS.get(node.kind)
    label = label_fn(node) if label_fn else node.kind
    return VNode(node.id, label, node.category, node.span,
                 [from_ast(c) for c in node.children()], ast_id=node.id)


def from_term(term: Term, ast_spans: dict[int, SourceSpan] | None = None) -> VNode:
    from ..semantics.render import op_symbol
    from ..semantics.terms import AssignT, CompT, ConstT, DenameT, IfT, SuperT, WhileT

    if isinstance(term, AssignT):
        label = f"AS^{term.var}"
    elif isinstance(term, CompT):
        label = "•"
    elif isinstance(term, IfT):
        label = "IF"
    elif isinstance(term, WhileT):
        label = "WH"
    elif isinstance(term, SuperT):
        label = f"S{'¹' if len(term.args) == 1 else '²'}({op_symbol(term.op)})"
    elif isinstance(term, (ConstT, DenameT)):
        label = render_text(term)
    else:
        label = render_text(term)
    span = ast_spans.get(term.ast_id) if ast_spans and term.ast_id is not None else None
    return VNode(term.id, label, "term", span, [from_term(c, ast_spans) for c in term.children()],
                 detail=term.sort, ast_id=term.ast_id)
