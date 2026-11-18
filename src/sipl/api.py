"""High-level API: one call from source text to every layer.

The CLI, the conformance adapter and the HTML visualizer all use these
functions, so the parser and the semantics live in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import __version__
from .diagnostics import Diagnostic, SiplSyntaxError
from .parser import ParseResult, parse
from .semantics.builder import BuildStep, build_term_with_steps
from .semantics.evaluator import DEFAULT_MAX_STEPS, EvalResult, evaluate
from .semantics.render import render_text
from .semantics.state import State
from .semantics.terms import Term

#: version of the JSON report format produced by :func:`analyze` (``sipl analyze``)
REPORT_SCHEMA_VERSION = 1


@dataclass
class Analysis:
    source: str
    parsed: ParseResult | None
    diagnostics: list[Diagnostic]
    term: Term | None = None
    steps: list[BuildStep] | None = None
    result: EvalResult | None = None

    @property
    def ok(self) -> bool:
        return self.parsed is not None


def analyze_source(source: str, state: State | None = None,
                   max_steps: int = DEFAULT_MAX_STEPS, strict: bool = False) -> Analysis:
    try:
        parsed = parse(source, strict=strict)
    except SiplSyntaxError as exc:
        return Analysis(source, None, [exc.diagnostic])
    term, steps = build_term_with_steps(parsed.ast, source)
    result = evaluate(term, state, max_steps=max_steps) if state is not None else None
    return Analysis(source, parsed, [], term, steps, result)


def report(analysis: Analysis, with_trace: bool = False) -> dict[str, Any]:
    """Implementation-independent JSON report (conformance adapter contract)."""
    data: dict[str, Any] = {
        "schema": REPORT_SCHEMA_VERSION,
        "implementation": f"sipl-semantics {__version__}",
        "syntax_ok": analysis.ok,
        "diagnostics": [d.to_dict() for d in analysis.diagnostics],
        "ast": None,
        "term": None,
        "result": None,
    }
    if analysis.parsed is not None and analysis.term is not None:
        data["ast"] = analysis.parsed.ast.to_sexpr()
        data["term"] = render_text(analysis.term, "ascii")
        data["term_unicode"] = render_text(analysis.term, "unicode")
        data["warnings"] = [d.to_dict() for d in analysis.parsed.warnings]
    if analysis.result is not None:
        data["result"] = analysis.result.to_dict(with_trace=with_trace)
    return data
