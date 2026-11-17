"""Diagnostics: errors bound to a SourceSpan with a human-readable explanation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .span import LineIndex, SourceSpan


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    span: SourceSpan
    severity: str = "error"
    hint: str | None = None
    expected: tuple[str, ...] = field(default_factory=tuple)

    @property
    def line(self) -> int:
        return self.span.start.line

    @property
    def column(self) -> int:
        return self.span.start.column

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "span": self.span.to_dict(),
        }
        if self.hint:
            data["hint"] = self.hint
        if self.expected:
            data["expected"] = list(self.expected)
        return data

    def render(self, source: str, filename: str = "<input>") -> str:
        """Render the diagnostic with the offending line and a caret marker."""
        index = LineIndex(source)
        line_no = self.span.start.line
        text = index.line_text(line_no) if source else ""
        width = max(1, min(self.span.length, max(1, len(text) - self.column + 1)))
        if self.span.start.line != self.span.end.line:
            width = max(1, len(text) - self.column + 1)
        gutter = f"{line_no:>4} | "
        out = [
            f"{filename}:{line_no}:{self.column}: {self.severity} [{self.code}]: {self.message}",
            gutter + text,
            " " * len(gutter) + " " * (self.column - 1) + "^" * width,
        ]
        if self.hint:
            out.append(" " * len(gutter) + f"підказка: {self.hint}")
        return "\n".join(out)


class SiplError(Exception):
    """Base error carrying a diagnostic."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class SiplSyntaxError(SiplError):
    """Lexical or syntax error."""
