"""Derivation tree in terms of the course BNF (practical work 1, VIS-01).

Inner nodes are the metavariables of the course (<програма>, <оператор>,
<вираз>, <умова>, <змінна>, <число>) annotated with the rule of table 1.4
(P1, S1-S6, A1-A6, B1-B5); leaves are the terminal symbols of the program,
numbered in left-to-right order. The left-to-right traversal of the leaves
must give back the program - this is exactly the check of syntactic
correctness from practical work 1.

The ambiguity of the course BNF is resolved by the priorities of the
textbook, so the tree is built from the AST (which already reflects them)
plus the tokens of the source.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import ast as A
from ..lexer import EOF, Token
from ..parser import ParseResult
from ..span import SourceSpan
from .model import VNode

CATEGORY = {"program": "<програма>", "stmt": "<оператор>", "aexpr": "<вираз>",
            "bexpr": "<умова>"}
_OP_RULES = {"+": "A3", "-": "A4", "*": "A5", "=": "B1", ">": "B2", "or": "B3",
             "/": "розш. div", "mod": "розш. mod", "<": "розш. <", "<=": "розш. ≤",
             "<>": "розш. ≠", ">=": "розш. ≥", "and": "розш. ∧"}


def _rule(node: A.Node) -> str:
    if isinstance(node, A.Program):
        return "P1"
    if isinstance(node, (A.BinOp, A.Compare, A.Logic)):
        return _OP_RULES[node.op]
    return {"Assign": "S1", "Seq": "S2", "If": "S3", "While": "S4", "Block": "S5",
            "Skip": "S6", "Num": "A1", "Var": "A2", "Not": "B4",
            "BoolLit": "розш. true/false"}[node.kind]


@dataclass
class _Builder:
    tokens: list[Token]
    next_id: int = 0
    leaf_no: int = 0

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def leaf(self, tok: Token) -> VNode:
        self.leaf_no += 1  # numbered later in traversal order
        return VNode(self._id(), tok.text, "token", tok.span)

    def tokens_in(self, span: SourceSpan, exclude: list[SourceSpan]) -> list[Token]:
        return [t for t in self.tokens if span.contains(t.span)
                and not any(e.contains(t.span) for e in exclude)]

    def build(self, node: A.Node) -> VNode:
        tree = self.core(node)
        cat = CATEGORY[node.category]
        rule = "B5" if node.category == "bexpr" else "A6"
        for span in node.paren_spans:  # innermost first:  (a) / (b)
            inner = tree.span
            assert inner is not None
            parens = self.tokens_in(span, [inner])
            tree = VNode(self._id(), f"{cat} {rule}", node.category, span,
                         [self.leaf(parens[0]), tree, self.leaf(parens[-1])], ast_id=node.id)
        return tree

    def core(self, node: A.Node) -> VNode:
        span = node.inner_span
        label = f"{CATEGORY[node.category]} {_rule(node)}"
        if isinstance(node, A.Num):
            toks = self.tokens_in(span, [])
            num = VNode(self._id(), "<число>", "rule", span, [self.leaf(t) for t in toks])
            return VNode(self._id(), label, node.category, span, [num], ast_id=node.id)
        if isinstance(node, A.Var):
            var = VNode(self._id(), "<змінна>", "rule", span,
                        [self.leaf(self.tokens_in(span, [])[0])])
            return VNode(self._id(), label, node.category, span, [var], ast_id=node.id)
        parts: list[tuple[int, VNode]] = []
        child_spans = [c.span for c in node.children()]
        if isinstance(node, A.Assign):
            child_spans.append(node.target_span)
            target_tok = self.tokens_in(node.target_span, [])[0]
            var = VNode(self._id(), "<змінна>", "rule", node.target_span,
                        [self.leaf(target_tok)])
            parts.append((node.target_span.start.offset, var))
        for child in node.children():
            parts.append((child.span.start.offset, self.build(child)))
        for tok in self.tokens_in(span, child_spans):
            parts.append((tok.span.start.offset, self.leaf(tok)))
        parts.sort(key=lambda p: p[0])
        return VNode(self._id(), label, node.category, span, [p[1] for p in parts],
                     ast_id=node.id)


def derivation_tree(parsed: ParseResult, numbered: bool = True) -> VNode:
    """Course-style derivation tree of the program; leaves are numbered 1, 2, ..."""
    tokens = [t for t in parsed.tokens if t.kind != EOF]
    root = _Builder(tokens).build(parsed.ast)
    leaves = [n for n in root.walk() if n.kind == "token"]
    # the left-to-right traversal of the leaves must give back the program
    if [lf.span for lf in leaves] != [t.span for t in tokens]:  # pragma: no cover
        raise AssertionError("derivation tree does not cover the program")
    if numbered:
        for i, lf in enumerate(leaves, 1):
            lf.detail = str(i)
            lf.label = f"{i}: {lf.label}"
    return root


def leaf_traversal(root: VNode) -> list[str]:
    """Terminal symbols in the order of the left-to-right traversal of the leaves."""
    return [n.label.split(": ", 1)[-1] for n in root.walk() if n.kind == "token"]


def traversal_report(root: VNode, parsed: ParseResult) -> str:
    """The syntactic correctness check of practical work 1."""
    leaves = [n for n in root.walk() if n.kind == "token"]
    numbered = " ".join(f"{n.detail} {n.label.split(': ', 1)[-1]}" for n in leaves)
    tokens = [t.text for t in parsed.tokens if t.kind != EOF]
    same = leaf_traversal(root) == tokens
    verdict = ("збігається з текстом програми ⇒ програма синтаксично правильна"
               if same else "НЕ збігається з текстом програми")
    return (f"Обхід листків зліва направо:\n  {numbered}\n"
            f"Отримана послідовність термінальних символів {verdict}.")
