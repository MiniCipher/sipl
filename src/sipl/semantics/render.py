"""Rendering of semantic terms: unicode (course notation), ascii, latex.

Rendering produces a :class:`Piece` tree in which every sub-term keeps its
``term_id``; this lets the HTML visualizer make each sub-term clickable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
)

STYLES = ("unicode", "ascii", "latex")

_OPS = {
    "unicode": {"+": "+", "-": "−", "*": "×", "/": "÷", "<": "<", "<=": "≤", "=": "=",
                "<>": "≠", ">": ">", ">=": "≥", "and": "∧", "or": "∨", "not": "¬"},
    "ascii": {"+": "+", "-": "-", "*": "*", "/": "/", "<": "<", "<=": "<=", "=": "=",
              "<>": "<>", ">": ">", ">=": ">=", "and": "and", "or": "or", "not": "not"},
    "latex": {"+": "+", "-": "-", "*": r"\cdot", "/": r"\div", "<": "<", "<=": r"\le",
              "=": "=", "<>": r"\ne", ">": ">", ">=": r"\ge", "and": r"\wedge",
              "or": r"\vee", "not": r"\neg"},
}
_COMP = {"unicode": " • ", "ascii": " o ", "latex": r" \bullet "}
_SUPERSCRIPT = {"1": "¹", "2": "²", "3": "³"}


def op_symbol(op: str, style: str = "unicode") -> str:
    return _OPS[style][op]


def overline(text: str) -> str:
    return "".join(ch + "̅" for ch in text)


@dataclass
class Piece:
    term_id: int | None
    parts: list[str | Piece] = field(default_factory=list)

    def text(self) -> str:
        return "".join(p if isinstance(p, str) else p.text() for p in self.parts)


def _assign_head(var: str, style: str) -> str:
    if style == "latex":
        return r"\mathrm{AS}^{" + var + "}"
    return f"AS^{var}"


def _name(name: str, style: str) -> str:
    return {"latex": r"\mathrm{" + name + "}"}.get(style, name)


def render(term: Term, style: str = "unicode") -> Piece:
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}")
    t = term
    if isinstance(t, AssignT):
        return Piece(t.id, [_assign_head(t.var, style) + "(", render(t.expr, style), ")"])
    if isinstance(t, CompT):
        parts: list[str | Piece] = []
        for i, comp in enumerate(t.flatten()):
            if i:
                parts.append(_COMP[style])
            parts.append(render(comp, style))
        return Piece(t.id, parts)
    if isinstance(t, IfT):
        return Piece(t.id, [_name("IF", style) + "(", render(t.cond, style), ", ",
                            render(t.then, style), ", ", render(t.other, style), ")"])
    if isinstance(t, WhileT):
        return Piece(t.id, [_name("WH", style) + "(", render(t.cond, style), ", ",
                            render(t.body, style), ")"])
    if isinstance(t, IdT):
        return Piece(t.id, [_name("id", style)])
    if isinstance(t, ConstT):
        if style == "unicode":
            txt = ("−" if t.value < 0 else "") + overline(str(abs(t.value)))
        elif style == "ascii":
            txt = f"#{t.value}"
        else:
            txt = r"\overline{" + str(t.value) + "}"
        return Piece(t.id, [txt])
    if isinstance(t, BoolConstT):
        letter = "T" if t.value else "F"
        txt = {"unicode": overline(letter), "ascii": f"#{letter}",
               "latex": r"\overline{" + letter + "}"}[style]
        return Piece(t.id, [txt])
    if isinstance(t, DenameT):
        arrow = {"unicode": "⇒", "ascii": "=>", "latex": r"\Rightarrow"}[style]
        return Piece(t.id, [f"{t.var}{arrow}"])
    if isinstance(t, SuperT):
        n = len(t.args)
        head = {"unicode": "S" + _SUPERSCRIPT.get(str(n), f"^{n}"), "ascii": f"S^{n}",
                "latex": f"S^{{{n}}}"}[style]
        parts = [head + "(" + op_symbol(t.op, style)]
        for a in t.args:
            parts += [", ", render(a, style)]
        parts.append(")")
        return Piece(t.id, parts)
    raise TypeError(f"unknown term {t!r}")


def render_text(term: Term, style: str = "unicode") -> str:
    return render(term, style).text()


def abbreviate(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_pretty(term: Term, style: str = "unicode", width: int = 80, indent: int = 0) -> str:
    """Multi-line layout: long compositions / IF / WH are broken over several lines."""
    flat = render_text(term, style)
    pad = " " * indent
    if len(flat) + indent <= width:
        return pad + flat
    if isinstance(term, CompT):
        comps = term.flatten()
        sep = _COMP[style].strip()
        lines = [render_pretty(comps[0], style, width, indent)]
        for c in comps[1:]:
            sub = render_pretty(c, style, width, indent + 2).lstrip()
            lines.append(pad + sep + " " + sub)
        return "\n".join(lines)
    if isinstance(term, (IfT, WhileT, AssignT, SuperT)):
        if isinstance(term, IfT):
            head, args = _name("IF", style), [term.cond, term.then, term.other]
        elif isinstance(term, WhileT):
            head, args = _name("WH", style), [term.cond, term.body]
        elif isinstance(term, AssignT):
            head, args = _assign_head(term.var, style), [term.expr]
        else:
            first = render(term, style).parts[0]
            head = str(first).split("(")[0]
            args = list(term.args)
        opener = head + "("
        if isinstance(term, SuperT):
            opener += op_symbol(term.op, style) + ","
        body = [render_pretty(a, style, width, indent + 4) for a in args]
        return pad + opener + "\n" + ",\n".join(body) + "\n" + pad + ")"
    return pad + flat
