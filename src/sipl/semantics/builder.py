"""Recursive construction of the semantic term from the AST (SEM-01).

Implements the rewriting rules of the textbook (Нікітченко, табл. 1.6) and
records every applied rule in the order of the textbook derivation
(top-down, like in the practicum example):

    sem_P(begin S end)          = sem_S(S)                               NS_Prog
    sem_S(x := a)               = AS^x(sem_A(a))                         NS_Stm_As
    sem_S(S1; S2)               = sem_S(S1) • sem_S(S2)                  NS_Stm_Seq
    sem_S(if b then S1 else S2) = IF(sem_B(b), sem_S(S1), sem_S(S2))     NS_Stm_If
    sem_S(while b do S)         = WH(sem_B(b), sem_S(S))                 NS_Stm_Wh
    sem_S(begin S end)          = (sem_S(S))                             NS_Stm_BE
    sem_S(skip)                 = id                                     NS_Stm_skip
    sem_A(n) = n̄                                                         NS_A_Num
    sem_A(x) = x⇒                                                        NS_A_Var
    sem_A(a1 + a2) = S²(add, sem_A(a1), sem_A(a2))                       NS_A_Add
    sem_A(a1 - a2) = S²(sub, sem_A(a1), sem_A(a2))                       NS_A_Sub
    sem_A(a1 * a2) = S²(mult, sem_A(a1), sem_A(a2))                      NS_A_Mult
    sem_A((a)) = sem_A(a)                                                NS_A_Par
    sem_B(a1 = a2) = S²(eq, sem_A(a1), sem_A(a2))                        NS_B_eq
    sem_B(a1 > a2) = S²(gr, sem_A(a1), sem_A(a2))                        NS_B_gr
    sem_B(b1 ∨ b2) = S²(or, sem_B(b1), sem_B(b2))                        NS_B_or
    sem_B(¬b)      = S¹(neg, sem_B(b))                                   NS_B_neg
    sem_B((b))     = sem_B(b)                                            NS_B_Par

Extensions (not in the course BNF) follow the same scheme and are marked
``ext``: NS_A_Div, NS_A_Mod, NS_B_less, NS_B_leq, NS_B_neq, NS_B_gre,
NS_B_and, NS_B_true, NS_B_false.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import ast as A
from .render import overline, render_text
from .terms import (
    CORE_OPS,
    OP_NAMES,
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

_OP_RULE = {"+": "NS_A_Add", "-": "NS_A_Sub", "*": "NS_A_Mult", "/": "NS_A_Div",
            "mod": "NS_A_Mod", "=": "NS_B_eq", ">": "NS_B_gr", "<": "NS_B_less",
            "<=": "NS_B_leq", "<>": "NS_B_neq", ">=": "NS_B_gre", "or": "NS_B_or",
            "and": "NS_B_and"}

#: rule name -> general rule (scheme), as in the textbook
RULE_SCHEMES = {
    "NS_Prog": "sem_P(begin S end) = sem_S(S)",
    "NS_Stm_As": "sem_S(x := a) = AS^x(sem_A(a))",
    "NS_Stm_Seq": "sem_S(S1; S2) = sem_S(S1) • sem_S(S2)",
    "NS_Stm_If": "sem_S(if b then S1 else S2) = IF(sem_B(b), sem_S(S1), sem_S(S2))",
    "NS_Stm_Wh": "sem_S(while b do S) = WH(sem_B(b), sem_S(S))",
    "NS_Stm_BE": "sem_S(begin S end) = (sem_S(S))",
    "NS_Stm_skip": "sem_S(skip) = id",
    "NS_A_Num": "sem_A(n) = n̄",
    "NS_A_Var": "sem_A(x) = x⇒",
    "NS_A_Par": "sem_A((a)) = sem_A(a)",
    "NS_B_Par": "sem_B((b)) = sem_B(b)",
    "NS_B_neg": "sem_B(¬b) = S¹(neg, sem_B(b))",
    "NS_B_true": "sem_B(true) = true̅  (розширення)",
    "NS_B_false": "sem_B(false) = false̅  (розширення)",
}
for _op, _rule in _OP_RULE.items():
    _sym = {"or": "∨", "and": "∧", "<=": "≤", "<>": "≠", ">=": "≥", "/": "div",
            "mod": "mod"}.get(_op, _op)
    _cat = "B" if _op in ("or", "and") else "A"
    _res = "B" if _rule.startswith("NS_B") else "A"
    RULE_SCHEMES[_rule] = (
        f"sem_{_res}({_cat.lower()}1 {_sym} {_cat.lower()}2) = S²({OP_NAMES[_op]}, "
        f"sem_{_cat}({_cat.lower()}1), sem_{_cat}({_cat.lower()}2))"
        + ("" if _op in CORE_OPS else "  (розширення)"))
EXTENSION_RULES = frozenset(r for r, s in RULE_SCHEMES.items() if "розширення" in s)


@dataclass
class BuildStep:
    """One application of a rewriting rule (concrete instance of a rule scheme)."""

    ast_id: int
    rule: str
    lhs: str        # e.g. sem_S(R := 1)
    rhs: str        # e.g. AS^R(sem_A(1))   - right side of the concrete rule
    term: Term      # resulting term of this sub-record

    @property
    def rule_text(self) -> str:
        return RULE_SCHEMES[self.rule]

    @property
    def source(self) -> str:
        return self.lhs[6:-1]

    def to_dict(self) -> dict[str, Any]:
        return {"ast_id": self.ast_id, "rule": self.rule, "rule_text": self.rule_text,
                "lhs": self.lhs, "rhs": self.rhs, "source": self.source,
                "term": render_text(self.term, "unicode"),
                "term_ascii": render_text(self.term, "ascii"), "term_id": self.term.id,
                "extension": self.rule in EXTENSION_RULES}


def _sem(node: A.Node) -> str:
    return {"program": "sem_P", "stmt": "sem_S", "aexpr": "sem_A", "bexpr": "sem_B"}[
        node.category]


@dataclass
class TermBuilder:
    source: str = ""
    steps: list[BuildStep] = field(default_factory=list)

    def _text(self, span: object) -> str:
        from ..span import SourceSpan

        assert isinstance(span, SourceSpan)
        if not self.source:
            return "…"
        return span.snippet(self.source, 70)

    def _call(self, node: A.Node) -> str:
        """``sem_X(<source of node>)`` - a not yet rewritten sub-record."""
        return f"{_sem(node)}({self._text(node.span)})"

    def _step(self, node: A.Node, rule: str, lhs_span: object, rhs: str) -> BuildStep:
        step = BuildStep(node.id, rule, f"{_sem(node)}({self._text(lhs_span)})", rhs,
                         IdT())  # term filled in after the sub-records are built
        self.steps.append(step)
        return step

    def build(self, node: A.Node) -> Term:
        # parentheses: sem_A((a)) = sem_A(a), applied from the outermost level
        par_steps = []
        spans = list(reversed(node.paren_spans))  # outermost first
        for i, span in enumerate(spans):
            inner = spans[i + 1] if i + 1 < len(spans) else node.inner_span
            rule = "NS_B_Par" if node.category == "bexpr" else "NS_A_Par"
            par_steps.append(self._step(node, rule, span,
                                        f"{_sem(node)}({self._text(inner)})"))
        rule, rhs = self._rule(node)
        step = self._step(node, rule, node.inner_span, rhs)
        term = self._build(node)
        for s in [*par_steps, step]:
            s.term = term
        return term

    def _rule(self, n: A.Node) -> tuple[str, str]:
        c = self._call
        if isinstance(n, A.Program):
            return "NS_Prog", c(n.body)
        if isinstance(n, A.Assign):
            return "NS_Stm_As", f"AS^{n.target}({c(n.value)})"
        if isinstance(n, A.Seq):
            return "NS_Stm_Seq", f"{c(n.first)} • {c(n.second)}"
        if isinstance(n, A.If):
            return "NS_Stm_If", f"IF({c(n.cond)}, {c(n.then_branch)}, {c(n.else_branch)})"
        if isinstance(n, A.While):
            return "NS_Stm_Wh", f"WH({c(n.cond)}, {c(n.body)})"
        if isinstance(n, A.Block):
            return "NS_Stm_BE", f"({c(n.body)})"
        if isinstance(n, A.Skip):
            return "NS_Stm_skip", "id"
        if isinstance(n, A.Num):
            return "NS_A_Num", ("−" if n.value < 0 else "") + overline(str(abs(n.value)))
        if isinstance(n, A.Var):
            return "NS_A_Var", f"{n.name}⇒"
        if isinstance(n, A.BoolLit):
            return ("NS_B_true", overline("true")) if n.value else ("NS_B_false",
                                                                     overline("false"))
        if isinstance(n, (A.BinOp, A.Compare, A.Logic)):
            return _OP_RULE[n.op], f"S²({OP_NAMES[n.op]}, {c(n.left)}, {c(n.right)})"
        if isinstance(n, A.Not):
            return "NS_B_neg", f"S¹(neg, {c(n.operand)})"
        raise TypeError(f"unsupported AST node {n.kind}")

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
            # sem_S(begin S end) = (sem_S(S)): the block denotes the term of its body
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
    """Term + the list of applied rules in textbook (top-down) order."""
    builder = TermBuilder(source)
    term = builder.build(program)
    assign_ids(term)
    return term, builder.steps
