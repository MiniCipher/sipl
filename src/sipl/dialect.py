"""Core language of the course vs. extensions (CORE-01).

The course BNF (textbook, table 1.4) has only ``+ - *``, ``= >``, ``∨ ¬``.
Practicum tasks also use ``≥`` (gre), ``<`` (less), ``div``, ``mod``; these are
accepted as *extensions* and reported as warnings (W201), or as errors (E201)
in strict mode.
"""

from __future__ import annotations

from .diagnostics import Diagnostic
from .lexer import Token

#: canonical token kind -> (name of the function of the algebra, description)
EXTENSIONS: dict[str, tuple[str, str]] = {
    "/": ("div", "ціла частка div"),
    "mod": ("mod", "остача mod"),
    "<": ("less", "відношення <"),
    "<=": ("leq", "відношення ≤"),
    "<>": ("neq", "відношення ≠"),
    ">=": ("gre", "відношення ≥"),
    "and": ("and", "кон'юнкція ∧"),
    "true": ("true", "константа true"),
    "false": ("false", "константа false"),
}


def find_extensions(tokens: list[Token], strict: bool = False) -> list[Diagnostic]:
    """Diagnostics for every use of a construct outside the course BNF."""
    out = []
    for tok in tokens:
        if tok.kind in EXTENSIONS:
            name, what = EXTENSIONS[tok.kind]
            fn = what if name in ("true", "false") else f"{what}, функція {name}"
            out.append(Diagnostic(
                "E201" if strict else "W201",
                f"'{tok.text}' ({fn}) - розширення, якого немає в БНФ курсу",
                tok.span, severity="error" if strict else "warning",
                hint="БНФ курсу: a ::= n | x | a1+a2 | a1-a2 | a1*a2 | (a);  "
                     "b ::= a1=a2 | a1>a2 | b1∨b2 | ¬b | (b)"))
    return out
