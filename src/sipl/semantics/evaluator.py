"""Evaluation of a semantic term on a state with a trace of applied rules (SEM-02).

Rules (st is a state, ∇ is overlay, ⊥ means "undefined"):

    [AS]     AS^x(A)(st)        = st ∇ [x ↦ A(st)]
    [SEQ]    (P1 • P2)(st)      = P2(P1(st))
    [IF-T]   IF(B, P1, P2)(st)  = P1(st),               if B(st) = T
    [IF-F]   IF(B, P1, P2)(st)  = P2(st),               if B(st) = F
    [WH-T]   WH(B, P)(st)       = WH(B, P)(P(st)),      if B(st) = T
    [WH-F]   WH(B, P)(st)       = st,                   if B(st) = F
    [ID]     id(st)             = st
    [CONST]  n̄(st) = n          [BCONST]  T̄(st) = T,  F̄(st) = F
    [DEN]    x⇒(st) = st(x)      (⊥ if x ∉ dom st)
    [ARITH]  S²(∘, A1, A2)(st)  = A1(st) ∘ A2(st)     (÷ by 0 gives ⊥)
    [REL]    S²(ρ, A1, A2)(st)  = A1(st) ρ A2(st)
    [AND]/[OR]  S²(∧/∨, B1, B2)(st) - strong Kleene logic on partial predicates
    [NOT]    S¹(¬, B)(st)       = ¬B(st)

Every function is partial: when a value is undefined, the result of the
whole program is ⊥ and the trace shows the rule where undefinedness arose.
WH is the least fixed point; it is computed by unfolding, and a configurable
step limit stops potentially non-terminating computations (result: ⊥ with
reason ``STEP_LIMIT`` - the evaluator does not *decide* termination).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .render import abbreviate, op_symbol, render_text
from .state import State, format_state
from .terms import (
    ARITH,
    RELATIONS,
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
)

DEFAULT_MAX_STEPS = 10_000

RULE_DESCRIPTIONS = {
    "AS": "AS^x(A)(st) = st ∇ [x ↦ A(st)]",
    "SEQ": "(P1 • P2)(st) = P2(P1(st))",
    "IF-T": "IF(B, P1, P2)(st) = P1(st), якщо B(st) = T",
    "IF-F": "IF(B, P1, P2)(st) = P2(st), якщо B(st) = F",
    "WH-T": "WH(B, P)(st) = WH(B, P)(P(st)), якщо B(st) = T",
    "WH-F": "WH(B, P)(st) = st, якщо B(st) = F",
    "ID": "id(st) = st",
    "CONST": "n̄(st) = n",
    "BCONST": "T̄(st) = T, F̄(st) = F",
    "DEN": "x⇒(st) = st(x), ⊥ якщо x ∉ dom(st)",
    "ARITH": "S²(∘, A1, A2)(st) = A1(st) ∘ A2(st)",
    "REL": "S²(ρ, A1, A2)(st) = A1(st) ρ A2(st)",
    "AND": "S²(∧, B1, B2)(st) = B1(st) ∧ B2(st) (сильна логіка Кліні)",
    "OR": "S²(∨, B1, B2)(st) = B1(st) ∨ B2(st) (сильна логіка Кліні)",
    "NOT": "S¹(¬, B)(st) = ¬B(st)",
}
PROGRAM_RULES = frozenset({"AS", "SEQ", "IF-T", "IF-F", "WH-T", "WH-F", "ID"})


class UndefinedValue(Exception):
    """A partial function is undefined on the given state."""

    def __init__(self, code: str, message: str, term: Term) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.term = term


class StepLimitExceeded(Exception):
    def __init__(self, term: Term, limit: int) -> None:
        super().__init__(f"step limit {limit} exceeded")
        self.term = term
        self.limit = limit


@dataclass
class TraceEntry:
    index: int
    depth: int
    rule: str
    term_id: int
    ast_id: int | None
    term_text: str
    state_in: int
    level: str  # "program" | "expr"
    parent: int | None = None
    state_out: int | None = None
    value: int | bool | None = None
    explanation: str = ""
    undefined: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "depth": self.depth, "rule": self.rule,
            "term_id": self.term_id, "ast_id": self.ast_id, "term": self.term_text,
            "state_in": self.state_in, "state_out": self.state_out, "value": self.value,
            "level": self.level, "parent": self.parent, "explanation": self.explanation,
            "undefined": self.undefined,
        }


@dataclass
class Transition:
    index: int
    before: int
    after: int
    var: str
    value: int
    term_id: int
    ast_id: int | None
    trace_index: int

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class EvalResult:
    status: str  # "defined" | "undefined"
    initial: State
    final: State | None
    states: list[State]
    trace: list[TraceEntry]
    transitions: list[Transition]
    steps: int
    reason: str | None = None
    reason_code: str | None = None
    error_term_id: int | None = None
    error_ast_id: int | None = None

    @property
    def defined(self) -> bool:
        return self.status == "defined"

    def to_dict(self, with_trace: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": self.status,
            "initial_state": self.initial,
            "final_state": self.final,
            "steps": self.steps,
        }
        if not self.defined:
            data["undefined"] = {"code": self.reason_code, "reason": self.reason,
                                 "term_id": self.error_term_id, "ast_id": self.error_ast_id}
        if with_trace:
            data["states"] = self.states
            data["transitions"] = [t.to_dict() for t in self.transitions]
            data["trace"] = [e.to_dict() for e in self.trace]
        return data


def _tv(b: bool) -> str:
    return "T" if b else "F"


def _int_div(a: int, b: int) -> int:
    """Integer division truncated toward zero (÷)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


@dataclass
class Evaluator:
    max_steps: int = DEFAULT_MAX_STEPS
    style: str = "unicode"
    term_width: int = 48
    states: list[State] = field(default_factory=list)
    trace: list[TraceEntry] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    _stack: list[int] = field(default_factory=list)

    # ------------------------------------------------------------- helpers
    def _t(self, term: Term) -> str:
        return abbreviate(render_text(term, self.style), self.term_width)

    def _st(self, i: int) -> str:
        return f"st{i}"

    def _enter(self, rule: str, term: Term, si: int, level: str) -> TraceEntry:
        if len(self.trace) >= self.max_steps:
            raise StepLimitExceeded(term, self.max_steps)
        entry = TraceEntry(
            index=len(self.trace), depth=len(self._stack), rule=rule, term_id=term.id,
            ast_id=term.ast_id, term_text=self._t(term), state_in=si, level=level,
            parent=self._stack[-1] if self._stack else None)
        self.trace.append(entry)
        return entry

    def _mark_undefined(self, entry: TraceEntry, exc: UndefinedValue) -> None:
        entry.undefined = True
        if not entry.explanation:
            text = f"({entry.term_text})" if entry.rule == "SEQ" else entry.term_text
            entry.explanation = (f"{text}({self._st(entry.state_in)}) = ⊥ "
                                 f"(невизначено, бо {exc.message})")

    # ------------------------------------------------------------- public
    def run(self, term: Term, state: State) -> EvalResult:
        self.states = [dict(state)]
        self.trace, self.transitions, self._stack = [], [], []
        try:
            final_idx = self.exec(term, 0)
        except UndefinedValue as exc:
            return self._undefined(state, exc.code, exc.message, exc.term)
        except StepLimitExceeded as exc:
            msg = (f"перевищено ліміт у {exc.limit} кроків обчислення: можливо, програма не "
                   "завершується (WH не досягає точки виходу) - результат вважається ⊥")
            return self._undefined(state, "STEP_LIMIT", msg, exc.term)
        return EvalResult("defined", dict(state), self.states[final_idx], self.states,
                          self.trace, self.transitions, len(self.trace))

    def _undefined(self, state: State, code: str, msg: str, term: Term) -> EvalResult:
        return EvalResult("undefined", dict(state), None, self.states, self.trace,
                          self.transitions, len(self.trace), msg, code, term.id, term.ast_id)

    # ------------------------------------------------------ program terms
    def exec(self, t: Term, si: int) -> int:
        rule = {AssignT: "AS", CompT: "SEQ", IfT: "IF", WhileT: "WH", IdT: "ID"}.get(type(t))
        if rule is None:
            raise TypeError(f"{t.kind} is not a program term")
        if isinstance(t, WhileT):
            return self._exec_while(t, si)
        entry = self._enter(rule, t, si, "program")
        self._stack.append(entry.index)
        try:
            out = self._exec_body(t, si, entry)
        except UndefinedValue as exc:
            self._mark_undefined(entry, exc)
            raise
        finally:
            self._stack.pop()
        entry.state_out = out
        return out

    def _exec_body(self, t: Term, si: int, entry: TraceEntry) -> int:
        st = self._st
        if isinstance(t, AssignT):
            value = self.eval_f(t.expr, si)
            new = dict(self.states[si])
            new[t.var] = value
            self.states.append(new)
            so = len(self.states) - 1
            self.transitions.append(Transition(len(self.transitions), si, so, t.var, value,
                                               t.id, t.ast_id, entry.index))
            entry.value = value
            entry.explanation = (f"{entry.term_text}({st(si)}) = {st(si)} ∇ [{t.var} ↦ {value}]"
                                 f" = {st(so)} = {format_state(new, self.style)}")
            return so
        if isinstance(t, CompT):
            p1, p2 = self._t(t.first), self._t(t.second)
            mid = self.exec(t.first, si)
            so = self.exec(t.second, mid)
            entry.explanation = (f"({p1} • {p2})({st(si)}) = P2(P1({st(si)})) = "
                                 f"P2({st(mid)}) = {st(so)}")
            return so
        if isinstance(t, IfT):
            b = self.eval_p(t.cond, si)
            entry.rule = "IF-T" if b else "IF-F"
            branch = t.then if b else t.other
            so = self.exec(branch, si)
            entry.explanation = (f"B({st(si)}) = {_tv(b)}, де B = {self._t(t.cond)} ⇒ "
                                 f"IF(...)({st(si)}) = {'P1' if b else 'P2'}({st(si)}) = {st(so)}")
            return so
        if isinstance(t, IdT):
            entry.explanation = f"id({st(si)}) = {st(si)}"
            return si
        raise TypeError(t)

    def _exec_while(self, t: WhileT, si: int) -> int:
        st = self._st
        iteration = 0
        while True:
            iteration += 1
            entry = self._enter("WH", t, si, "program")
            self._stack.append(entry.index)
            try:
                b = self.eval_p(t.cond, si)
                if not b:
                    entry.rule = "WH-F"
                    entry.state_out = si
                    entry.explanation = (f"ітерація {iteration}: B({st(si)}) = F, де B = "
                                         f"{self._t(t.cond)} ⇒ WH(B, P)({st(si)}) = {st(si)}")
                    return si
                entry.rule = "WH-T"
                so = self.exec(t.body, si)
                entry.state_out = so
                entry.explanation = (f"ітерація {iteration}: B({st(si)}) = T ⇒ WH(B, P)({st(si)})"
                                     f" = WH(B, P)(P({st(si)})) = WH(B, P)({st(so)})")
            except UndefinedValue as exc:
                self._mark_undefined(entry, exc)
                raise
            finally:
                self._stack.pop()
            si = so

    # --------------------------------------------------- function terms
    def eval_f(self, t: Term, si: int) -> int:
        v = self._eval(t, si)
        assert isinstance(v, int) and not isinstance(v, bool)
        return v

    def eval_p(self, t: Term, si: int) -> bool:
        v = self._eval(t, si)
        assert isinstance(v, bool)
        return v

    def _eval(self, t: Term, si: int) -> int | bool:
        if isinstance(t, ConstT):
            rule = "CONST"
        elif isinstance(t, BoolConstT):
            rule = "BCONST"
        elif isinstance(t, DenameT):
            rule = "DEN"
        elif isinstance(t, SuperT):
            rule = ("ARITH" if t.op in ARITH else "REL" if t.op in RELATIONS
                    else t.op.upper())
        else:
            raise TypeError(f"{t.kind} is not an expression term")
        entry = self._enter(rule, t, si, "expr")
        self._stack.append(entry.index)
        try:
            value = self._eval_body(t, si, entry)
        except UndefinedValue as exc:
            self._mark_undefined(entry, exc)
            raise
        finally:
            self._stack.pop()
        entry.value = value
        entry.state_out = si
        return value

    def _eval_body(self, t: Term, si: int, entry: TraceEntry) -> int | bool:
        st = self._st(si)
        if isinstance(t, ConstT):
            entry.explanation = f"{entry.term_text}({st}) = {t.value}"
            return t.value
        if isinstance(t, BoolConstT):
            entry.explanation = f"{entry.term_text}({st}) = {_tv(t.value)}"
            return t.value
        if isinstance(t, DenameT):
            state = self.states[si]
            if t.var not in state:
                entry.explanation = (f"{entry.term_text}({st}) = ⊥: змінна {t.var} не має "
                                     f"значення у стані {st} ({t.var} ∉ dom {st})")
                raise UndefinedValue("UNBOUND", f"змінна {t.var} не визначена у стані {st}", t)
            v = state[t.var]
            entry.explanation = f"{entry.term_text}({st}) = {st}({t.var}) = {v}"
            return v
        assert isinstance(t, SuperT)
        sym = op_symbol(t.op, self.style)
        n = "¹" if len(t.args) == 1 else "²"
        head = f"S{n}({sym}, …)({st})"
        if t.op == "not":
            b = self.eval_p(t.args[0], si)
            entry.explanation = f"{head} = ¬{_tv(b)} = {_tv(not b)}"
            return not b
        if t.op in ("and", "or"):
            left = self._try_p(t.args[0], si)
            right = self._try_p(t.args[1], si)
            show = {True: "T", False: "F", None: "⊥"}
            if t.op == "and":
                res = False if (left is False or right is False) else (
                    True if (left and right) else None)
            else:
                res = True if (left is True or right is True) else (
                    False if (left is False and right is False) else None)
            entry.explanation = f"{head} = {show[left]} {sym} {show[right]} = {show[res]}"
            if res is None:
                raise UndefinedValue("UNDEFINED_CONDITION",
                                     f"умова {self._t(t)} невизначена у стані {st}", t)
            return res
        a = self.eval_f(t.args[0], si)
        b2 = self.eval_f(t.args[1], si)
        if t.op in ARITH:
            if t.op == "/" and b2 == 0:
                entry.explanation = f"{head} = {a} {sym} 0 = ⊥ (ділення на нуль)"
                raise UndefinedValue("DIV_ZERO", f"ділення на нуль у {self._t(t)}", t)
            val = {"+": a + b2, "-": a - b2, "*": a * b2}.get(t.op)
            if val is None:
                val = _int_div(a, b2)
            entry.explanation = f"{head} = {a} {sym} {b2} = {val}"
            return val
        res2 = {"<": a < b2, "<=": a <= b2, "=": a == b2, "<>": a != b2, ">": a > b2,
                ">=": a >= b2}[t.op]
        entry.explanation = f"{head} = {a} {sym} {b2} = {_tv(res2)}"
        return res2

    def _try_p(self, t: Term, si: int) -> bool | None:
        try:
            return self.eval_p(t, si)
        except UndefinedValue:
            return None


def evaluate(term: Term, state: State, max_steps: int = DEFAULT_MAX_STEPS,
             style: str = "unicode") -> EvalResult:
    """Apply the semantic term to the state; returns final state or ⊥ with the full trace."""
    return Evaluator(max_steps=max_steps, style=style).run(term, state)
