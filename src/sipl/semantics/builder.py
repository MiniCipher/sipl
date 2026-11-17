"""Recursive construction of the semantic term from the AST (SEM-01).

Construction rules (⟦·⟧ is the semantic mapping):

    ⟦x := a⟧                  = AS^x(⟦a⟧)
    ⟦S1 ; S2⟧                 = ⟦S1⟧ • ⟦S2⟧
    ⟦if b then S1 else S2⟧    = IF(⟦b⟧, ⟦S1⟧, ⟦S2⟧)
    ⟦while b do S⟧            = WH(⟦b⟧, ⟦S⟧)
    ⟦begin S end⟧             = ⟦S⟧
    ⟦skip⟧                    = id
    ⟦n⟧ = n̄     ⟦x⟧ = x⇒     ⟦true⟧ = T̄     ⟦false⟧ = F̄
    ⟦a1 ∘ a2⟧                 = S²(∘, ⟦a1⟧, ⟦a2⟧)    for ∘ ∈ {+, −, ×, ÷}
    ⟦a1 ρ a2⟧                 = S²(ρ, ⟦a1⟧, ⟦a2⟧)    for ρ ∈ {<, ≤, =, ≠, >, ≥}
    ⟦b1 and b2⟧ = S²(∧, ⟦b1⟧, ⟦b2⟧)   ⟦b1 or b2⟧ = S²(∨, ⟦b1⟧, ⟦b2⟧)
    ⟦not b⟧                   = S¹(¬, ⟦b⟧)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import ast as A
from .render import render_text
from .terms import (
    AssignT,
    BoolConstT,
    CompT,
    ConstT,
    DenameT,
    IdT,
    IfT,
    SuperT,
    Term,
    WhileT,
    assign_ids,
)

RULES = {
    "Assign": ("T-AS", "⟦x := a⟧ = AS^x(⟦a⟧)"),
    "Seq": ("T-SEQ", "⟦S1 ; S2⟧ = ⟦S1⟧ • ⟦S2⟧"),
    "If": ("T-IF", "⟦if b then S1 else S2⟧ = IF(⟦b⟧, ⟦S1⟧, ⟦S2⟧)"),
    "While": ("T-WH", "⟦while b do S⟧ = WH(⟦b⟧, ⟦S⟧)"),
    "Block": ("T-BLOCK", "⟦begin S end⟧ = ⟦S⟧"),
    "Skip": ("T-SKIP", "⟦skip⟧ = id"),
    "Num": ("T-CONST", "⟦n⟧ = n̄"),
    "Var": ("T-DEN", "⟦x⟧ = x⇒"),
    "BinOp": ("T-ARITH", "⟦a1 ∘ a2⟧ = S²(∘, ⟦a1⟧, ⟦a2⟧)"),
    "BoolLit": ("T-BCONST", "⟦true⟧ = T̄, ⟦false⟧ = F̄"),
    "Compare": ("T-REL", "⟦a1 ρ a2⟧ = S²(ρ, ⟦a1⟧, ⟦a2⟧)"),
    "Logic": ("T-LOGIC", "⟦b1 ∧/∨ b2⟧ = S²(∧/∨, ⟦b1⟧, ⟦b2⟧)"),
    "Not": ("T-NOT", "⟦not b⟧ = S¹(¬, ⟦b⟧)"),
}


@dataclass
class BuildStep:
    """One application of a construction rule (for the explanation of SEM-01)."""

    ast_id: int
    rule: str
    rule_text: str
    source: str
    term: Term

    def to_dict(self) -> dict[str, Any]:
        return {"ast_id": self.ast_id, "rule": self.rule, "rule_text": self.rule_text,
                "source": self.source, "term": render_text(self.term, "unicode"),
                "term_ascii": render_text(self.term, "ascii"), "term_id": self.term.id}


@dataclass
class TermBuilder:
    source: str = ""
    steps: list[BuildStep] = field(default_factory=list)

    def build(self, node: A.Node) -> Term:
        term = self._build(node)
        if isinstance(node, A.Program):
            return term
        rule, text = RULES[node.kind]
        snippet = node.span.snippet(self.source, 50) if self.source else node.to_sexpr()
        self.steps.append(BuildStep(node.id, rule, text, snippet, term))
        return term

    def _build(self, n: A.Node) -> Term:
        if isinstance(n, A.Program):
            return self.build(n.body)
        if isinstance(n, A.Assign):
            return AssignT(var=n.target, expr=self.build(n.value), ast_id=n.id)
        if isinstance(n, A.Seq):
            return CompT(first=self.build(n.first), second=self.build(n.second), ast_id=n.id)
        if isinstance(n, A.If):
            return IfT(cond=self.build(n.cond), then=self.build(n.then_branch),
                       other=self.build(n.else_branch), ast_id=n.id)
        if isinstance(n, A.While):
            return WhileT(cond=self.build(n.cond), body=self.build(n.body), ast_id=n.id)
        if isinstance(n, A.Block):
            # begin/end is pure grouping: the term of the body is the term of the block
            return self.build(n.body)
        if isinstance(n, A.Skip):
            return IdT(ast_id=n.id)
        if isinstance(n, A.Num):
            return ConstT(value=n.value, ast_id=n.id)
        if isinstance(n, A.Var):
            return DenameT(var=n.name, ast_id=n.id)
        if isinstance(n, A.BoolLit):
            return BoolConstT(value=n.value, ast_id=n.id)
        if isinstance(n, (A.BinOp, A.Compare, A.Logic)):
            return SuperT(op=n.op, args=[self.build(n.left), self.build(n.right)], ast_id=n.id)
        if isinstance(n, A.Not):
            return SuperT(op="not", args=[self.build(n.operand)], ast_id=n.id)
        raise TypeError(f"unsupported AST node {n.kind}")


def build_term(program: A.Node, source: str = "") -> Term:
    """Build the semantic term for an AST node (usually :class:`~sipl.ast.Program`)."""
    term, _ = build_term_with_steps(program, source)
    return term


def build_term_with_steps(program: A.Node, source: str = "") -> tuple[Term, list[BuildStep]]:
    builder = TermBuilder(source)
    term = builder.build(program)
    assign_ids(term)
    return term, builder.steps
