"""Lexical analysis of SIPL (see grammar/LEXICAL.md).

Alternative spellings are different characters for the same terminal (the
textbook itself writes both ``M–N`` with an en dash and ``R ∗ X``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Diagnostic, SiplSyntaxError
from .span import LineIndex, SourceSpan

KEYWORDS = frozenset(
    {"begin", "end", "if", "then", "else", "while", "do", "skip", "true", "false",
     "and", "or", "not", "div", "mod"}
)

#: alternative spellings -> canonical token kind
WORD_ALIASES = {"div": "/"}

#: operators, longest first
OPERATORS: list[tuple[str, str]] = [
    (":=", ":="), ("<=", "<="), (">=", ">="), ("<>", "<>"), ("!=", "<>"),
    ("&&", "and"), ("||", "or"),
    (";", ";"), ("(", "("), (")", ")"), ("+", "+"), ("-", "-"), ("−", "-"), ("–", "-"),
    ("*", "*"), ("∗", "*"), ("×", "*"), ("%", "mod"), ("/", "/"), ("÷", "/"), ("<", "<"), (">", ">"),
    ("=", "="), ("≤", "<="), ("≥", ">="), ("≠", "<>"), ("∧", "and"), ("&", "and"),
    ("∨", "or"), ("¬", "not"), ("!", "not"),
]

IDENT = "IDENT"
NUMBER = "NUMBER"
EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: str  # canonical kind: IDENT, NUMBER, EOF, keyword or operator
    text: str  # exact source text
    span: SourceSpan

    def describe(self) -> str:
        if self.kind == EOF:
            return "кінець файлу"
        if self.kind == IDENT:
            return f"ідентифікатор '{self.text}'"
        if self.kind == NUMBER:
            return f"число {self.text}"
        return f"'{self.text}'"


def _is_ident_start(ch: str) -> bool:
    return ch == "_" or ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def _is_ident_char(ch: str) -> bool:
    return _is_ident_start(ch) or ch.isdigit()


def tokenize(source: str) -> list[Token]:
    """Split source into tokens. Raises :class:`SiplSyntaxError` on lexical errors."""
    index = LineIndex(source)
    tokens: list[Token] = []
    i, n = 0, len(source)

    def error(code: str, msg: str, start: int, end: int, hint: str | None = None) -> SiplSyntaxError:
        return SiplSyntaxError(Diagnostic(code, msg, index.span(start, end), hint=hint))

    while i < n:
        ch = source[i]
        if ch in " \t\r\n\f\v﻿":
            i += 1
            continue
        if source.startswith("//", i):
            j = source.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "{":
            j = source.find("}", i + 1)
            if j < 0:
                raise error("E001", "незакритий коментар '{'", i, i + 1,
                            hint="блоковий коментар має закінчуватися символом '}'")
            i = j + 1
            continue
        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            if j < n and _is_ident_start(source[j]):
                k = j
                while k < n and _is_ident_char(source[k]):
                    k += 1
                raise error("E002", f"некоректний ідентифікатор '{source[i:k]}'", i, k,
                            hint="ідентифікатор не може починатися з цифри")
            tokens.append(Token(NUMBER, source[i:j], index.span(i, j)))
            i = j
            continue
        if _is_ident_start(ch):
            j = i
            while j < n and _is_ident_char(source[j]):
                j += 1
            word = source[i:j]
            kind = WORD_ALIASES.get(word, word) if word in KEYWORDS else IDENT
            tokens.append(Token(kind, word, index.span(i, j)))
            i = j
            continue
        for text, kind in OPERATORS:
            if source.startswith(text, i):
                tokens.append(Token(kind, text, index.span(i, i + len(text))))
                i += len(text)
                break
        else:
            if ch == ":":
                raise error("E003", "очікувалось ':=' після ':'", i, i + 1,
                            hint="присвоювання в SIPL записується як ':='")
            raise error("E004", f"невідомий символ {ch!r}", i, i + 1)
    # EOF is placed right after the last token, so "unexpected end" errors point
    # to the line where the program actually ends
    end = tokens[-1].span.end.offset if tokens else 0
    tokens.append(Token(EOF, "", index.span(end, end)))
    return tokens
