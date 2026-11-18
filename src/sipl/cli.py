"""Command line interface: ``sipl <command> FILE [options]``.

Exit codes (stable):
    0  success (for ``eval``: the result is defined)
    1  syntax / lexical error in the program
    2  usage error: bad arguments, unreadable file, malformed state
    3  ``eval``: the result is undefined (⊥)
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path
from typing import Any

from . import __version__
from .api import analyze_source, report
from .diagnostics import Diagnostic, SiplSyntaxError
from .ebnf import Grammar
from .parser import ParseResult, parse
from .semantics.builder import EXTENSION_RULES, build_term_with_steps
from .semantics.evaluator import DEFAULT_MAX_STEPS, PROGRAM_RULES, EvalResult, evaluate
from .semantics.render import render_pretty, render_text
from .semantics.state import State, StateFormatError, format_state, parse_state
from .visualization import (
    build_payload,
    derivation_tree,
    from_ast,
    from_parse_tree,
    from_term,
    render_html,
    to_dot,
    to_json,
    to_svg,
    to_text,
    traversal_report,
)

EXIT_OK, EXIT_SYNTAX, EXIT_USAGE, EXIT_UNDEFINED = 0, 1, 2, 3


class UsageError(Exception):
    pass


# ------------------------------------------------------------------ helpers

def _read_source(args: argparse.Namespace) -> tuple[str, str]:
    if getattr(args, "code", None) is not None:
        return args.code, "<code>"
    if args.file is None:
        raise UsageError("вкажіть файл програми або код через -c \"...\"")
    if args.file == "-":
        return sys.stdin.read(), "<stdin>"
    path = Path(args.file)
    try:
        return path.read_text(encoding="utf-8"), str(path)
    except OSError as exc:
        raise UsageError(f"не вдалося прочитати файл {path}: {exc.strerror}") from None
    except UnicodeDecodeError:
        raise UsageError(f"файл {path} не є текстом у кодуванні UTF-8") from None


def _state(args: argparse.Namespace) -> State | None:
    if getattr(args, "state", None) is None:
        return None
    try:
        return parse_state(args.state)
    except StateFormatError as exc:
        raise UsageError(str(exc)) from None


def _emit(text: str, args: argparse.Namespace, kind: str = "") -> None:
    out = getattr(args, "output", None)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"записано {kind + ' ' if kind else ''}у {out}", file=sys.stderr)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _print_diag(diag: Diagnostic, source: str, filename: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"ok": False, "file": filename, "diagnostics": [diag.to_dict()]},
                         ensure_ascii=False, indent=2))
    else:
        print(diag.render(source, filename), file=sys.stderr)


def _parse_or_report(args: argparse.Namespace) -> tuple[ParseResult, str] | None:
    source, filename = _read_source(args)
    try:
        return parse(source, strict=getattr(args, "strict", False)), filename
    except SiplSyntaxError as exc:
        _print_diag(exc.diagnostic, source, filename, getattr(args, "json", False))
        return None


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------- commands

def cmd_check(args: argparse.Namespace) -> int:
    res = _parse_or_report(args)
    if res is None:
        return EXIT_SYNTAX
    parsed, filename = res
    stmts = sum(1 for n in parsed.ast.walk() if n.kind in ("Assign", "If", "While", "Skip"))
    core = not parsed.warnings
    if args.json:
        print(_dump({"ok": True, "file": filename, "core_language": core,
                     "diagnostics": [d.to_dict() for d in parsed.warnings],
                     "statements": stmts, "variables": parsed.ast.variables()}))
    else:
        for w in parsed.warnings:
            print(w.render(parsed.source, filename), file=sys.stderr)
        lang = ("мова ядра курсу" if core
                else f"використано розширення: {len(parsed.warnings)} (див. вище; --strict - "
                     "лише ядро курсу)")
        print(f"{filename}: OK - синтаксично коректна програма "
              f"({stmts} операторів, змінні: {', '.join(parsed.ast.variables()) or '-'}; {lang})")
    return EXIT_OK


def cmd_parse(args: argparse.Namespace) -> int:
    res = _parse_or_report(args)
    if res is None:
        return EXIT_SYNTAX
    parsed, filename = res
    fmt = args.format
    ast = parsed.ast
    if fmt == "sexpr":
        _emit(ast.to_sexpr(), args)
    elif fmt == "json":
        _emit(_dump(ast.to_dict(with_spans=not args.no_spans)), args)
    else:
        v = from_ast(ast)
        text = {"text": lambda: to_text(v, parsed.source),
                "dot": lambda: to_dot(v, parsed.source, f"AST: {filename}"),
                "svg": lambda: to_svg(v, parsed.source, f"AST: {filename}")}[fmt]()
        _emit(text, args, fmt.upper())
    return EXIT_OK


def cmd_tree(args: argparse.Namespace) -> int:
    res = _parse_or_report(args)
    if res is None:
        return EXIT_SYNTAX
    parsed, filename = res
    if args.format == "html":
        term, steps = build_term_with_steps(parsed.ast, parsed.source)
        _emit(render_html(build_payload(parsed, term, steps, None, None, filename)), args, "HTML")
        return EXIT_OK
    if args.style == "course":
        v = derivation_tree(parsed)
        title = f"Дерево синтаксичного виводу (БНФ курсу): {filename}"
    else:
        v = from_parse_tree(parsed.tree, compact=args.compact)
        title = f"Parse tree (grammar/sipl-ext.ebnf): {filename}"
    text = {"text": lambda: to_text(v, parsed.source) + (
                "\n\n" + traversal_report(v, parsed) if args.style == "course" else ""),
            "json": lambda: to_json(v, parsed.source),
            "dot": lambda: to_dot(v, parsed.source, title),
            "svg": lambda: to_svg(v, parsed.source, title)}[args.format]()
    _emit(text, args, args.format.upper())
    return EXIT_OK


def cmd_term(args: argparse.Namespace) -> int:
    res = _parse_or_report(args)
    if res is None:
        return EXIT_SYNTAX
    parsed, filename = res
    term, steps = build_term_with_steps(parsed.ast, parsed.source)
    if args.json:
        _emit(_dump({"file": filename, "term": render_text(term, "unicode"),
                     "term_ascii": render_text(term, "ascii"),
                     "term_latex": render_text(term, "latex"),
                     "tree": term.to_dict(), "steps": [s.to_dict() for s in steps]}), args)
        return EXIT_OK
    if args.tree:
        spans = {n.id: n.span for n in parsed.ast.walk()}
        v = from_term(term, spans)
        title = f"Semantic term: {filename}"
        text = {"text": lambda: to_text(v, parsed.source),
                "dot": lambda: to_dot(v, parsed.source, title),
                "svg": lambda: to_svg(v, parsed.source, title)}[args.tree]()
        _emit(text, args, args.tree.upper())
        return EXIT_OK
    lines = []
    if args.steps:
        lines.append("Побудова семантичного терму за правилами табл. 1.6 (зверху вниз):")
        for i, st in enumerate(steps, 1):
            mark = "  (розширення)" if st.rule in EXTENSION_RULES else ""
            lines.append(f"{i:>3}. {st.rule}{mark}: {st.lhs} = {st.rhs}")
        lines.append("")
        lines.append("Семантичний терм програми:")
    if args.pretty:
        lines.append(render_pretty(term, args.style, width=args.width))
    else:
        lines.append(render_text(term, args.style))
    _emit("\n".join(lines), args)
    return EXIT_OK


def _format_eval(result: EvalResult, args: argparse.Namespace) -> str:
    style = "ascii" if args.ascii else "unicode"
    out = [f"Початковий стан: st0 = {format_state(result.initial, style)}"]
    if args.explain:
        out.append("")
        out.append("Покрокове обчислення (трейс застосованих правил):")
        for e in result.trace:
            if not args.all_rules and e.rule not in PROGRAM_RULES:
                continue
            mark = " ⊥" if e.undefined else ""
            out.append(f"{e.index + 1:>5}. {'  ' * e.depth}[{e.rule}]{mark} {e.explanation}")
    out.append("")
    out.append("Переходи станів:")
    out.append(f"   st0 = {format_state(result.states[0], style)}")
    shown = result.transitions
    if len(shown) > 40 and not args.explain:
        shown = shown[:15] + shown[-15:]
    for i, t in enumerate(shown):
        if shown is not result.transitions and i == 15:
            out.append(f"   … ще {len(result.transitions) - 30} переходів (див. --explain або --json) …")
        out.append(f"   st{t.before} → st{t.after}  (AS^{t.var}: {t.var} ↦ {t.value})  "
                   f"st{t.after} = {format_state(result.states[t.after], style)}")
    out.append("")
    if result.defined:
        out.append(f"Результат: {format_state(result.final, style)}   "
                   f"[{result.steps} застосувань правил]")
    else:
        out.append(f"Результат: невизначений (⊥) - {result.reason}   [код {result.reason_code}]")
    return "\n".join(out)


def cmd_eval(args: argparse.Namespace) -> int:
    state = _state(args)
    res = _parse_or_report(args)
    if res is None:
        return EXIT_SYNTAX
    parsed, filename = res
    if state is None:
        state = {}
    term, _ = build_term_with_steps(parsed.ast, parsed.source)
    result = evaluate(term, state, max_steps=args.max_steps,
                      style="ascii" if args.ascii else "unicode")
    if args.json:
        data = {"file": filename, "term": render_text(term, "unicode")}
        data.update(result.to_dict(with_trace=True))
        _emit(_dump(data), args)
    else:
        if args.show_term:
            print("Семантичний терм: " + render_text(term, "ascii" if args.ascii else "unicode"))
        _emit(_format_eval(result, args), args)
    return EXIT_OK if result.defined else EXIT_UNDEFINED


def cmd_visualize(args: argparse.Namespace) -> int:
    state = _state(args)
    res = _parse_or_report(args)
    if res is None:
        return EXIT_SYNTAX
    parsed, filename = res
    term, steps = build_term_with_steps(parsed.ast, parsed.source)
    result = evaluate(term, state, max_steps=args.max_steps) if state is not None else None
    html = render_html(build_payload(parsed, term, steps, result, state, filename))
    out = args.output or (Path(filename).stem if not filename.startswith("<") else "program") + ".html"
    Path(out).write_text(html, encoding="utf-8")
    print(f"візуалізацію записано у {out}")
    if args.open:
        webbrowser.open(Path(out).resolve().as_uri())
    return EXIT_OK


def cmd_analyze(args: argparse.Namespace) -> int:
    state = _state(args)
    source, _ = _read_source(args)
    analysis = analyze_source(source, state, max_steps=args.max_steps, strict=args.strict)
    print(_dump(report(analysis, with_trace=args.trace)))
    if not analysis.ok:
        return EXIT_SYNTAX
    if analysis.result is not None and not analysis.result.defined:
        return EXIT_UNDEFINED
    return EXIT_OK


def cmd_grammar(args: argparse.Namespace) -> int:
    name = "sipl-ext.ebnf" if args.ext else "sipl.ebnf"
    if args.file is None and args.code is None:
        from importlib import resources

        print(resources.files("sipl").joinpath(f"data/{name}").read_text("utf-8"))
        return EXIT_OK
    grammar = Grammar.load(extended=args.ext)
    source, filename = _read_source(args)
    ok = grammar.accepts(source)
    lang = "розширеній мові (grammar/sipl-ext.ebnf)" if args.ext else \
        "мові ядра курсу (grammar/sipl.ebnf)"
    print(f"{filename}: {'належить' if ok else 'НЕ належить'} {lang}")
    return EXIT_OK if ok else EXIT_SYNTAX


# ------------------------------------------------------------------- parser

def _add_input(p: argparse.ArgumentParser) -> None:
    p.add_argument("file", nargs="?", help="файл .sipl ('-' - стандартний ввід)")
    p.add_argument("-c", "--code", help="текст програми замість файлу")
    p.add_argument("--strict", action="store_true",
                   help="лише мова ядра курсу (БНФ підручника); розширення - помилка E201")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="sipl",
        description="SIPL: аналізатор синтаксису та семантики (парсер, AST, семантичні терми, "
                    "покрокове обчислення, візуалізація).",
        epilog="Приклад: sipl eval examples/power.sipl --state \"X=2, Y=3\" --explain")
    ap.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("check", help="перевірити синтаксис програми")
    _add_input(p)
    p.add_argument("--json", action="store_true", help="вивід у JSON")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("parse", help="побудувати типізоване AST")
    _add_input(p)
    p.add_argument("-f", "--format", choices=["text", "json", "sexpr", "dot", "svg"],
                   default="text")
    p.add_argument("--no-spans", action="store_true", help="JSON без позицій")
    p.add_argument("-o", "--output", help="файл для результату")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("tree", help="дерево синтаксичного виводу (parse tree)")
    _add_input(p)
    p.add_argument("-f", "--format", choices=["text", "json", "dot", "svg", "html"],
                   default="text")
    p.add_argument("--style", choices=["course", "ebnf"], default="course",
                   help="course - за БНФ курсу (<оператор>, <вираз>, ..., як у ПР 1); "
                        "ebnf - за операційною граматикою sipl-ext.ebnf")
    p.add_argument("--compact", action="store_true",
                   help="(--style ebnf) згорнути ланцюжки одиничних правил")
    p.add_argument("-o", "--output", help="файл для результату")
    p.set_defaults(func=cmd_tree)

    p = sub.add_parser("term", help="побудувати семантичний терм програми")
    _add_input(p)
    p.add_argument("-s", "--style", choices=["unicode", "ascii", "latex"], default="unicode")
    p.add_argument("--pretty", action="store_true", help="багаторядковий вивід")
    p.add_argument("--width", type=int, default=80)
    p.add_argument("--steps", action="store_true", help="показати кроки рекурсивної побудови")
    p.add_argument("--tree", choices=["text", "dot", "svg"], help="терм як дерево")
    p.add_argument("--json", action="store_true")
    p.add_argument("-o", "--output", help="файл для результату")
    p.set_defaults(func=cmd_term)

    p = sub.add_parser("eval", help="обчислити терм на стані з покроковим поясненням")
    _add_input(p)
    p.add_argument("--state", "-s", help="початковий стан: \"X=2, Y=3\" або JSON")
    p.add_argument("--explain", "-e", action="store_true", help="трейс застосованих правил")
    p.add_argument("--all-rules", "-a", action="store_true",
                   help="разом з формулами для виразів (AF_S, AF_DNM, AF_CONST)")
    p.add_argument("--show-term", "-t", action="store_true", help="надрукувати терм")
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                   help=f"ліміт застосувань правил (за замовчуванням {DEFAULT_MAX_STEPS})")
    p.add_argument("--ascii", action="store_true", help="ASCII-нотація")
    p.add_argument("--json", action="store_true", help="повний результат і трейс у JSON")
    p.add_argument("-o", "--output", help="файл для результату")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("visualize", help="HTML: код → дерево → AST → терм → стани")
    _add_input(p)
    p.add_argument("--state", "-s", help="початковий стан: \"X=2, Y=3\" або JSON")
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    p.add_argument("-o", "--output", help="HTML-файл (за замовчуванням <ім'я>.html)")
    p.add_argument("--open", action="store_true", help="відкрити у браузері")
    p.set_defaults(func=cmd_visualize)

    p = sub.add_parser("analyze", help="JSON-звіт для conformance suite та інтеграцій")
    _add_input(p)
    p.add_argument("--state", "-s", help="початковий стан: \"X=2, Y=3\" або JSON")
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    p.add_argument("--trace", action="store_true", help="включити трейс у звіт")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("grammar", help="показати граматику EBNF або перевірити файл за нею")
    p.add_argument("file", nargs="?", help="перевірити належність програми мові граматики")
    p.add_argument("-c", "--code")
    p.add_argument("--ext", action="store_true", help="розширена граматика sipl-ext.ebnf")
    p.set_defaults(func=cmd_grammar)
    return ap


def _setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _setup_stdout()
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "command", None):
        ap.print_help()
        return EXIT_USAGE
    try:
        return int(args.func(args))
    except UsageError as exc:
        print(f"sipl: помилка: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
