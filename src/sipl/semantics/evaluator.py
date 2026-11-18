"""Application of a semantic term to a state with a trace of applied formulas (SEM-02).

Formulas of the textbook (Нікітченко, табл. 1.5; ∇ - overlay):

    (S^n(f, g1, ..., gn))(st) = f(g1(st), ..., gn(st))                     AF_S
    AS^x(fa)(st)   = st ∇ [x ↦ fa(st)]                                      AF_AS
    (fs1 • fs2)(st) = fs2(fs1(st))                                           AF_SEQ
    IF(fb, fs1, fs2)(st) = fs1(st), if fb(st) = true;  fs2(st), if false     AF_IF
    WH(fb, fs)(st) = st_n, where st_0 = st, st_k+1 = fs(st_k),
                     fb(st_0) = ... = fb(st_n-1) = true, fb(st_n) = false    AF_WH
    x⇒(st) = st(x)      (partial: undefined if x has no value in st)         AF_DNM
    id(st) = st                                                              AF_ID
    n̄(st) = n           (constant function, section 1.3.1)                   AF_CONST

Partiality (Зауваження 1.6): if the value of any function occurring in a
formula is undefined, the result is undefined (strict semantics - also for
``or``: S²(or, ⊥, true) is undefined, since or(g1(st), g2(st)) needs both values).

If the loop does not terminate, NumItWH and the value of WH are undefined.
Termination is undecidable, so the evaluator uses a step limit and reports
``STEP_LIMIT`` ("no result within N formula applications") - it does not
*decide* non-termination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .render import abbreviate, render_text
from .state import State, format_state
from .terms import (
    ARITH,
    OP_NAMES,
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
    "AF_S": "(Sⁿ(f, g1, …, gn))(st) = f(g1(st), …, gn(st))",
    "AF_AS": "ASˣ(fa)(st) = st ∇ [x ↦ fa(st)]",
    "AF_SEQ": "(fs1 • fs2)(st) = fs2(fs1(st))",
    "AF_IF": "IF(fb, fs1, fs2)(st) = fs1(st), якщо fb(st) = true; fs2(st), якщо fb(st) = false",
    "AF_WH": "WH(fb, fs)(st) = stₙ, де st₀ = st, stₖ₊₁ = fs(stₖ), fb(st₀) = … = fb(stₙ₋₁) = "
             "true, fb(stₙ) = false",
    "AF_DNM": "x⇒(st) = st(x)  (не визначено, якщо x не має значення в st)",
    "AF_ID": "id(st) = st",
    "AF_CONST": "n̄(st) = n",
}
PROGRAM_RULES = frozenset({"AF_AS", "AF_SEQ", "AF_IF", "AF_WH", "AF_ID"})


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
    note: str = ""  # e.g. "true-гілка", "ітерація 2", "вихід із циклу"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "depth": self.depth, "rule": self.rule, "note": self.note,
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


def show_value(v: int | bool | None) -> str:
    if v is None:
        return "⊥"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _apply(op: str, a: int, b: int) -> int | bool:
    """Basic functions of the algebra on Int (div/mod: floor division, b ≠ 0)."""
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a // b
    if op == "mod":
        return a % b
    return {"<": a < b, "<=": a <= b, "=": a == b, "<>": a != b, ">": a > b,
            ">=": a >= b}[op]


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
    def _t(self, term: Term, width: int | None = None) -> str:
        return abbreviate(render_text(term, self.style), width or self.term_width)

    def _st(self, i: int) -> str:
        return f"st{i}"

    def _state(self, i: int) -> str:
        return format_state(self.states[i], self.style)

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
            text = f"({entry.term_text})" if entry.rule == "AF_SEQ" else entry.term_text
            entry.explanation = (f"{text}({self._st(entry.state_in)}) не визначене, "
                                 f"бо {exc.message} (Зауваження 1.6)")

    # ------------------------------------------------------------- public
    def run(self, term: Term, state: State) -> EvalResult:
        self.states = [dict(state)]
        self.trace, self.transitions, self._stack = [], [], []
        try:
            final_idx = self.exec(term, 0)
        except UndefinedValue as exc:
            return self._undefined(state, exc.code, exc.message, exc.term)
        except StepLimitExceeded as exc:
            for e in self.trace:  # unfinished applications (e.g. the loop itself)
                if e.state_out is not None:
                    continue
                e.undefined = True
                if not e.explanation:
                    e.explanation = (f"{e.term_text}({self._st(e.state_in)}): результат не "
                                     f"отримано за {exc.limit} застосувань формул")
            msg = (f"за {exc.limit} застосувань формул результат не отримано: цикл, імовірно, "
                   "не завершується (NumItWH невизначене) - значення вважається невизначеним")
            return self._undefined(state, "STEP_LIMIT", msg, exc.term)
        return EvalResult("defined", dict(state), self.states[final_idx], self.states,
                          self.trace, self.transitions, len(self.trace))

    def _undefined(self, state: State, code: str, msg: str, term: Term) -> EvalResult:
        return EvalResult("undefined", dict(state), None, self.states, self.trace,
                          self.transitions, len(self.trace), msg, code, term.id, term.ast_id)

    # ------------------------------------------------------ program terms
    def exec(self, t: Term, si: int) -> int:
        rule = {AssignT: "AF_AS", CompT: "AF_SEQ", IfT: "AF_IF", WhileT: "AF_WH",
                IdT: "AF_ID"}.get(type(t))
        if rule is None:
            raise TypeError(f"{t.kind} is not a program term")
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
            fa = self._t(t.expr, 30)
            entry.explanation = (f"{entry.term_text}({st(si)}) = {st(si)} ∇ [{t.var} ↦ "
                                 f"{fa}({st(si)})] = {st(si)} ∇ [{t.var} ↦ {value}] = "
                                 f"{format_state(new, self.style)} = {st(so)}")
            return so
        if isinstance(t, CompT):
            fs1, fs2 = self._t(t.first, 30), self._t(t.second, 30)
            mid = self.exec(t.first, si)
            so = self.exec(t.second, mid)
            entry.explanation = (f"({fs1} • {fs2})({st(si)}) = fs2(fs1({st(si)})) = "
                                 f"fs2({st(mid)}) = {st(so)}")
            return so
        if isinstance(t, IfT):
            b = self.eval_p(t.cond, si)
            entry.note = "fb = true" if b else "fb = false"
            so = self.exec(t.then if b else t.other, si)
            which = "fs1" if b else "fs2"
            entry.explanation = (f"IF(fb, fs1, fs2)({st(si)}), fb = {self._t(t.cond, 30)}: "
                                 f"fb({st(si)}) = {show_value(b)} ⇒ {which}({st(si)}) = {st(so)}")
            return so
        if isinstance(t, WhileT):
            return self._exec_while(t, si, entry)
        if isinstance(t, IdT):
            entry.explanation = f"id({st(si)}) = {st(si)}"
            return si
        raise TypeError(t)

    def _exec_while(self, t: WhileT, si: int, entry: TraceEntry) -> int:
        """AF_WH: st_0 = st, st_k+1 = fs(st_k) while fb(st_k) = true."""
        st = self._st
        start = si
        seq = [si]
        k = 0
        fb = self._t(t.cond, 30)
        while True:
            check = self._enter("AF_WH", t, si, "program")
            self._stack.append(check.index)
            try:
                b = self.eval_p(t.cond, si)
                if not b:
                    check.note = f"fb(st{k}′) = false"
                    check.state_out = si
                    check.explanation = (f"fb(st{k}′) = {fb}({st(si)}) = false ⇒ цикл "
                                         f"завершено, n = NumItWH = {k}")
                    break
                check.note = f"ітерація {k + 1}"
                so = self.exec(t.body, si)
                check.state_out = so
                check.explanation = (f"ітерація {k + 1}: fb(st{k}′) = {fb}({st(si)}) = true ⇒ "
                                     f"st{k + 1}′ = fs(st{k}′) = fs({st(si)}) = {st(so)}")
            except UndefinedValue as exc:
                self._mark_undefined(check, exc)
                raise
            finally:
                self._stack.pop()
            si = so
            seq.append(si)
            k += 1
        chain = ", ".join(f"st{i}′ = {st(s)}" for i, s in enumerate(seq[:4]))
        if len(seq) > 4:
            chain += f", …, st{len(seq) - 1}′ = {st(seq[-1])}"
        entry.note = f"NumItWH = {k}"
        entry.explanation = (f"WH(fb, fs)({st(start)}) = st{k}′ = {st(si)}, де {chain}; "
                             + ("fb(st0′) = true" if k == 1 else
                                f"fb = true на st0′…st{k - 1}′")
                             + f", fb(st{k}′) = false"
                             if k else
                             f"WH(fb, fs)({st(start)}) = st0′ = {st(start)}, бо fb({st(start)}) "
                             f"= false (жодної ітерації)")
        return si

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
        if isinstance(t, (ConstT, BoolConstT)):
            rule = "AF_CONST"
        elif isinstance(t, DenameT):
            rule = "AF_DNM"
        elif isinstance(t, SuperT):
            rule = "AF_S"
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
        if isinstance(t, (ConstT, BoolConstT)):
            entry.explanation = f"{entry.term_text}({st}) = {show_value(t.value)}"
            return t.value
        if isinstance(t, DenameT):
            state = self.states[si]
            if t.var not in state:
                entry.explanation = (f"{t.var}⇒({st}) не визначене: змінна {t.var} не має "
                                     f"значення у стані {st} = {self._state(si)}")
                raise UndefinedValue("UNBOUND", f"{t.var}⇒({st}) не визначене "
                                     f"({t.var} не має значення у {st})", t)
            v = state[t.var]
            entry.explanation = f"{t.var}⇒({st}) = {st}({t.var}) = {v}"
            return v
        assert isinstance(t, SuperT)
        name = OP_NAMES[t.op]
        n = "¹" if len(t.args) == 1 else "²"
        args = [self._t(a, 24) for a in t.args]
        head = (f"S{n}({name}, {', '.join(args)})({st}) = "
                f"{name}({', '.join(f'{a}({st})' for a in args)})")
        # strict superposition: every argument must be defined (Зауваження 1.6)
        values = [self._eval(a, si) for a in t.args]
        shown = ", ".join(show_value(v) for v in values)
        if t.op == "not":
            res: int | bool = not values[0]
        elif t.op in ("and", "or"):
            res = (values[0] and values[1]) if t.op == "and" else (values[0] or values[1])
        else:
            a, b = values
            assert isinstance(a, int) and isinstance(b, int)
            if t.op in ("/", "mod") and b == 0:
                entry.explanation = f"{head} = {name}({shown}) не визначене (ділення на 0)"
                raise UndefinedValue("DIV_ZERO", f"{name}({a}, 0) не визначене", t)
            res = _apply(t.op, a, b)
        assert t.op in ARITH or t.op in RELATIONS or t.op in ("and", "or", "not")
        entry.explanation = f"{head} = {name}({shown}) = {show_value(res)}"
        return res


def evaluate(term: Term, state: State, max_steps: int = DEFAULT_MAX_STEPS,
             style: str = "unicode") -> EvalResult:
    """Apply the semantic term to the state; returns the final state or ⊥ with the trace."""
    return Evaluator(max_steps=max_steps, style=style).run(term, state)
