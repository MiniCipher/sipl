"""Concrete syntax tree (parse tree / дерево синтаксичного виводу).

Inner nodes are labelled with the grammar rule names of ``grammar/sipl.ebnf``;
leaves are tokens. Every node carries its SourceSpan, so the tree can be
linked back to the source code (VIS-01).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .lexer import Token
from .span import SourceSpan


@dataclass(eq=False)
class ParseNode:
    label: str
    span: SourceSpan
    children: list[ParseNode] = field(default_factory=list)
    token: Token | None = None
    id: int = -1

    @property
    def is_leaf(self) -> bool:
        return self.token is not None

    def walk(self) -> Iterator[ParseNode]:
        yield self
        for child in self.children:
            yield from child.walk()

    def compact(self) -> ParseNode:
        """Collapse chains of single-child inner nodes (aexpr -> term -> factor -> ...).

        The resulting node label shows the collapsed chain, e.g. ``aexpr›term›factor``.
        """
        node = self
        labels = [node.label]
        while not node.is_leaf and len(node.children) == 1 and not node.children[0].is_leaf:
            node = node.children[0]
            labels.append(node.label)
        if node.is_leaf:
            return ParseNode(node.label, node.span, [], node.token, node.id)
        label = "›".join(labels) if len(labels) > 1 else node.label
        return ParseNode(label, node.span, [c.compact() for c in node.children], None, node.id)

    def to_dict(self, source: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "label": self.label, "span": self.span.to_dict()}
        if self.token is not None:
            data["token"] = {"kind": self.token.kind, "text": self.token.text}
        else:
            data["children"] = [c.to_dict(source) for c in self.children]
        if source is not None:
            data["text"] = self.span.text(source)
        return data

    def display_label(self) -> str:
        if self.token is None:
            return self.label
        if self.token.kind in ("IDENT", "NUMBER"):
            return f"{self.token.kind} {self.token.text}"
        return repr(self.token.text) if self.token.text else self.token.kind


def assign_ids(root: ParseNode) -> None:
    for i, node in enumerate(root.walk()):
        node.id = i
