"""Recursive-descent parser: tokens -> parse tree (CST) -> typed AST (CORE-02).

The parser follows ``grammar/sipl.ebnf`` rule by rule; each rule produces a
:class:`~sipl.cst.ParseNode` labelled with the rule name. The AST is then built
from the parse tree by :func:`build_ast` (our own node classes, not a raw
library tree).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import ast as A
from .cst import ParseNode
from .cst import assign_ids as assign_cst_ids
from .diagnostics import Diagnostic, SiplSyntaxError
from .lexer import EOF, IDENT, NUMBER, Token, tokenize
from .span import SourceSpan

STATEMENT_START = (IDENT, "if", "while", "begin", "skip")
REL_OPS = ("<", "<=", "=", "<>", ">", ">=")


class _ParseFailure(Exception):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _describe_expected(kinds: tuple[str, ...]) -> str:
    names = {IDENT: "ідентифікатор", NUMBER: "число", EOF: "кінець файлу"}
    return ", ".join(names.get(k, f"'{k}'") for k in kinds)


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ------------------------------------------------------------ helpers
    @property
    def tok(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, k: int = 1) -> Token:
        return self.tokens[min(self.pos + k, len(self.tokens) - 1)]

    def at(self, *kinds: str) -> bool:
        return self.tok.kind in kinds

    def leaf(self) -> ParseNode:
        tok = self.tok
        self.pos += 1
        return ParseNode(tok.kind, tok.span, token=tok)

    def fail(self, expected: tuple[str, ...], message: str | None = None,
             hint: str | None = None, code: str = "E100") -> _ParseFailure:
        tok = self.tok
        msg = message or f"очікувалось {_describe_expected(expected)}, але знайдено {tok.describe()}"
        return _ParseFailure(Diagnostic(code, msg, tok.span, hint=hint, expected=expected))

    def expect(self, kind: str, hint: str | None = None) -> ParseNode:
        if self.tok.kind != kind:
            raise self.fail((kind,), hint=hint)
        return self.leaf()

    @staticmethod
    def node(label: str, children: list[ParseNode]) -> ParseNode:
        span = SourceSpan.merge(children[0].span, children[-1].span)
        return ParseNode(label, span, children)

    # ------------------------------------------------------------ program
    def parse_program(self) -> ParseNode:
        if self.at(EOF):
            raise self.fail(STATEMENT_START, "порожня програма: очікувався оператор",
                            hint="найпростіша коректна програма: skip", code="E101")
        seq = self.parse_stmt_seq()
        if not self.at(EOF):
            if self.at(*STATEMENT_START):
                raise self.fail((";",), f"пропущено ';' перед {self.tok.describe()}",
                                hint="оператори послідовності розділяються ';'", code="E102")
            if self.at("end"):
                raise self.fail((EOF,), "зайве 'end' без відповідного 'begin'", code="E103")
            raise self.fail((";", EOF))
        return self.node("program", [seq])

    def parse_stmt_seq(self) -> ParseNode:
        children = [self.parse_statement()]
        while self.at(";"):
            semi = self.leaf()
            children.append(semi)
            if self.at("end", EOF):
                raise _ParseFailure(Diagnostic(
                    "E104", f"зайва ';' перед {self.tok.describe()}", semi.span,
                    hint="';' у SIPL - роздільник операторів, а не їх завершення",
                    expected=STATEMENT_START))
            children.append(self.parse_statement())
        return self.node("stmt_seq", children)

    def parse_statement(self) -> ParseNode:
        kind = self.tok.kind
        if kind == IDENT:
            inner = self.parse_assignment()
        elif kind == "if":
            inner = self.parse_if()
        elif kind == "while":
            inner = self.parse_while()
        elif kind == "begin":
            inner = self.parse_block()
        elif kind == "skip":
            inner = self.node("skip_stmt", [self.leaf()])
        else:
            hint = None
            if kind == ";":
                hint = "порожній оператор у SIPL записується як skip"
            elif kind == NUMBER:
                hint = "ліворуч від ':=' має бути змінна"
            elif kind == "else":
                hint = "перед 'else' не ставиться ';'"
            raise self.fail(STATEMENT_START,
                            f"очікувався оператор, але знайдено {self.tok.describe()}",
                            hint=hint, code="E105")
        return self.node("statement", [inner])

    def parse_assignment(self) -> ParseNode:
        target = self.leaf()
        if self.at("="):
            raise self.fail((":=",), "очікувалось ':=' у присвоюванні, знайдено '='",
                            hint="'=' - це порівняння; присвоювання записується як ':='",
                            code="E106")
        op = self.expect(":=")
        return self.node("assignment", [target, op, self.parse_aexpr()])

    def parse_if(self) -> ParseNode:
        kw = self.leaf()
        cond = self.parse_bexpr()
        then_kw = self.expect("then")
        then_branch = self.parse_statement()
        if self.at(";") and self.peek().kind == "else":
            raise self.fail(STATEMENT_START, "зайва ';' перед 'else'",
                            hint="у SIPL перед 'else' не ставиться ';'", code="E107")
        if not self.at("else"):
            raise self.fail(("else",), hint="оператор if у SIPL завжди має гілку else "
                            "(можна написати 'else skip')", code="E108")
        else_kw = self.leaf()
        else_branch = self.parse_statement()
        return self.node("if_stmt", [kw, cond, then_kw, then_branch, else_kw, else_branch])

    def parse_while(self) -> ParseNode:
        kw = self.leaf()
        cond = self.parse_bexpr()
        do_kw = self.expect("do")
        body = self.parse_statement()
        return self.node("while_stmt", [kw, cond, do_kw, body])

    def parse_block(self) -> ParseNode:
        begin = self.leaf()
        if self.at("end"):
            raise self.fail(STATEMENT_START, "порожній блок begin end",
                            hint="використайте 'begin skip end'", code="E109")
        seq = self.parse_stmt_seq()
        if not self.at("end"):
            if self.at(EOF):
                raise _ParseFailure(Diagnostic(
                    "E110", f"незакритий 'begin' (відкрито у {begin.span.start})",
                    self.tok.span, hint="додайте відповідне 'end'", expected=("end",)))
            if self.at(*STATEMENT_START):
                raise self.fail((";", "end"), f"пропущено ';' перед {self.tok.describe()}",
                                hint="оператори в блоці розділяються ';'", code="E102")
            raise self.fail((";", "end"))
        return self.node("block", [begin, seq, self.leaf()])

    # -------------------------------------------------------- arithmetic
    def parse_aexpr(self) -> ParseNode:
        children = [self.parse_term()]
        while self.at("+", "-"):
            children.append(self.node("addop", [self.leaf()]))
            children.append(self.parse_term())
        return self.node("aexpr", children)

    def parse_term(self) -> ParseNode:
        children = [self.parse_factor()]
        while self.at("*", "/"):
            children.append(self.node("mulop", [self.leaf()]))
            children.append(self.parse_factor())
        return self.node("term", children)

    def parse_factor(self) -> ParseNode:
        if self.at(NUMBER, IDENT):
            return self.node("factor", [self.leaf()])
        if self.at("("):
            lp = self.leaf()
            inner = self.parse_aexpr()
            rp = self.expect(")")
            return self.node("factor", [lp, inner, rp])
        hint = None
        if self.at("true", "false"):
            hint = "логічні константи не можна використовувати в арифметичному виразі"
        raise self.fail((NUMBER, IDENT, "("),
                        f"очікувався арифметичний вираз, але знайдено {self.tok.describe()}",
                        hint=hint, code="E111")

    # -------------------------------------------------------- conditions
    def parse_bexpr(self) -> ParseNode:
        children = [self.parse_bterm()]
        while self.at("or"):
            children.append(self.leaf())
            children.append(self.parse_bterm())
        return self.node("bexpr", children)

    def parse_bterm(self) -> ParseNode:
        children = [self.parse_bfactor()]
        while self.at("and"):
            children.append(self.leaf())
            children.append(self.parse_bfactor())
        return self.node("bterm", children)

    def parse_bfactor(self) -> ParseNode:
        if self.at("not"):
            kw = self.leaf()
            return self.node("bfactor", [kw, self.parse_bfactor()])
        if self.at("true", "false"):
            return self.node("bfactor", [self.leaf()])
        if self.at("("):
            # ambiguity "(" bexpr ")" vs. comparison starting with "(" -> backtrack
            saved = self.pos
            try:
                lp = self.leaf()
                inner = self.parse_bexpr()
                rp = self.expect(")")
                return self.node("bfactor", [lp, inner, rp])
            except _ParseFailure as first:
                bexpr_error = first
                self.pos = saved
            try:
                return self.node("bfactor", [self.parse_comparison()])
            except _ParseFailure as second:
                # report the alternative that got further into the input
                if second.diagnostic.span.start >= bexpr_error.diagnostic.span.start:
                    raise
                raise bexpr_error from None
        return self.node("bfactor", [self.parse_comparison()])

    def parse_comparison(self) -> ParseNode:
        left = self.parse_aexpr()
        if not self.at(*REL_OPS):
            hint = None
            if self.at(":="):
                hint = "у умові порівняння на рівність записується як '='"
            raise self.fail(REL_OPS, f"очікувалась операція порівняння, але знайдено "
                            f"{self.tok.describe()}", hint=hint, code="E112")
        op = self.node("relop", [self.leaf()])
        return self.node("comparison", [left, op, self.parse_aexpr()])


# ======================================================================
#                          parse tree  ->  AST
# ======================================================================

def _tok(node: ParseNode) -> Token:
    assert node.token is not None
    return node.token


def _build_stmt_seq(node: ParseNode) -> A.Stmt:
    stmts = [_build_statement(c) for c in node.children if c.label == "statement"]
    result = stmts[0]
    for nxt in stmts[1:]:  # ';' is left-associative
        result = A.Seq(first=result, second=nxt, span=SourceSpan.merge(result.span, nxt.span))
    return result


def _build_statement(node: ParseNode) -> A.Stmt:
    inner = node.children[0]
    c = inner.children
    if inner.label == "assignment":
        return A.Assign(target=_tok(c[0]).text, target_span=c[0].span,
                        value=_build_aexpr(c[2]), span=inner.span)
    if inner.label == "if_stmt":
        return A.If(cond=_build_bexpr(c[1]), then_branch=_build_statement(c[3]),
                    else_branch=_build_statement(c[5]), span=inner.span)
    if inner.label == "while_stmt":
        return A.While(cond=_build_bexpr(c[1]), body=_build_statement(c[3]), span=inner.span)
    if inner.label == "block":
        return A.Block(body=_build_stmt_seq(c[1]), span=inner.span)
    if inner.label == "skip_stmt":
        return A.Skip(span=inner.span)
    raise AssertionError(f"unexpected statement {inner.label}")


def _op_text(node: ParseNode) -> str:
    leaf = node.children[0] if node.children else node
    return _tok(leaf).kind


def _fold_arith(node: ParseNode, build: Callable[[ParseNode], A.AExpr]) -> A.AExpr:
    # left fold for rules of the form  x { op x }  (left associativity)
    items = node.children
    result = build(items[0])
    for i in range(1, len(items), 2):
        right = build(items[i + 1])
        result = A.BinOp(op=_op_text(items[i]), left=result, right=right,
                         span=SourceSpan.merge(result.span, right.span))
    return result


def _fold_logic(node: ParseNode, build: Callable[[ParseNode], A.BExpr]) -> A.BExpr:
    items = node.children
    result = build(items[0])
    for i in range(1, len(items), 2):
        right = build(items[i + 1])
        result = A.Logic(op=_op_text(items[i]), left=result, right=right,
                         span=SourceSpan.merge(result.span, right.span))
    return result


def _build_aexpr(node: ParseNode) -> A.AExpr:
    return _fold_arith(node, _build_term)


def _build_term(node: ParseNode) -> A.AExpr:
    return _fold_arith(node, _build_factor)


def _build_factor(node: ParseNode) -> A.AExpr:
    first = node.children[0]
    if first.token is not None and first.token.kind == NUMBER:
        return A.Num(value=int(first.token.text), span=node.span)
    if first.token is not None and first.token.kind == IDENT:
        return A.Var(name=first.token.text, span=node.span)
    inner = _build_aexpr(node.children[1])
    inner.span = node.span  # include the parentheses
    return inner


def _build_bexpr(node: ParseNode) -> A.BExpr:
    return _fold_logic(node, _build_bterm)


def _build_bterm(node: ParseNode) -> A.BExpr:
    return _fold_logic(node, _build_bfactor)


def _build_bfactor(node: ParseNode) -> A.BExpr:
    c = node.children
    first = c[0]
    if first.token is not None:
        kind = first.token.kind
        if kind == "not":
            return A.Not(operand=_build_bfactor(c[1]), span=node.span)
        if kind in ("true", "false"):
            return A.BoolLit(value=kind == "true", span=node.span)
        if kind == "(":
            inner = _build_bexpr(c[1])
            inner.span = node.span
            return inner
    comp = first
    return A.Compare(op=_op_text(comp.children[1]), left=_build_aexpr(comp.children[0]),
                     right=_build_aexpr(comp.children[2]), span=comp.span)


def build_ast(tree: ParseNode) -> A.Program:
    program = A.Program(body=_build_stmt_seq(tree.children[0]), span=tree.span)
    A.assign_ids(program)
    return program


# ======================================================================
#                                public API
# ======================================================================

@dataclass
class ParseResult:
    source: str
    tree: ParseNode
    ast: A.Program
    tokens: list[Token]


def parse_tree(source: str) -> tuple[ParseNode, list[Token]]:
    """Parse source into a parse tree. Raises :class:`SiplSyntaxError`."""
    tokens = tokenize(source)
    parser = Parser(tokens)
    try:
        tree = parser.parse_program()
    except _ParseFailure as exc:
        raise SiplSyntaxError(exc.diagnostic) from None
    assign_cst_ids(tree)
    return tree, tokens


def parse(source: str) -> ParseResult:
    """Parse SIPL source into parse tree + typed AST. Raises :class:`SiplSyntaxError`."""
    tree, tokens = parse_tree(source)
    return ParseResult(source, tree, build_ast(tree), tokens)


def parse_program(source: str) -> A.Program:
    return parse(source).ast
