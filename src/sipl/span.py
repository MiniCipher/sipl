"""Source positions and spans (CORE-02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, order=True)
class SourcePos:
    """A position in the source text.

    ``offset`` is a 0-based character offset; ``line`` and ``column`` are 1-based.
    """

    offset: int
    line: int
    column: int

    def to_dict(self) -> dict[str, int]:
        return {"offset": self.offset, "line": self.line, "column": self.column}

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(frozen=True)
class SourceSpan:
    """A half-open range ``[start, end)`` of the source text."""

    start: SourcePos
    end: SourcePos

    @staticmethod
    def merge(first: SourceSpan, last: SourceSpan) -> SourceSpan:
        return SourceSpan(min(first.start, last.start), max(first.end, last.end))

    def contains(self, other: SourceSpan) -> bool:
        return self.start.offset <= other.start.offset and other.end.offset <= self.end.offset

    def contains_offset(self, offset: int) -> bool:
        return self.start.offset <= offset < self.end.offset

    @property
    def length(self) -> int:
        return self.end.offset - self.start.offset

    def text(self, source: str) -> str:
        return source[self.start.offset : self.end.offset]

    def snippet(self, source: str, limit: int = 40) -> str:
        """One-line abbreviated fragment of the source covered by the span."""
        raw = " ".join(self.text(source).split())
        if len(raw) > limit:
            raw = raw[: limit - 1] + "…"
        return raw

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


class LineIndex:
    """Converts character offsets into (line, column) positions."""

    def __init__(self, source: str) -> None:
        self.source = source
        self._starts = [0]
        for i, ch in enumerate(source):
            if ch == "\n":
                self._starts.append(i + 1)

    def pos(self, offset: int) -> SourcePos:
        lo, hi = 0, len(self._starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return SourcePos(offset, lo + 1, offset - self._starts[lo] + 1)

    def span(self, start: int, end: int) -> SourceSpan:
        return SourceSpan(self.pos(start), self.pos(end))

    def line_text(self, line: int) -> str:
        start = self._starts[line - 1]
        end = self.source.find("\n", start)
        return self.source[start:] if end < 0 else self.source[start:end]
