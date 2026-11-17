# Командний рядок `sipl`

Кожна команда приймає файл (`FILE`, або `-` для stdin) чи код через `-c "..."`.

| Команда | Що робить | Основні опції |
|---|---|---|
| `sipl check FILE` | перевірка синтаксису | `--json` |
| `sipl parse FILE` | типізоване AST | `-f text\|json\|sexpr\|dot\|svg`, `--no-spans`, `-o` |
| `sipl tree FILE` | дерево синтаксичного виводу | `-f text\|json\|dot\|svg\|html`, `--compact`, `-o` |
| `sipl term FILE` | семантичний терм | `-s unicode\|ascii\|latex`, `--steps`, `--pretty`, `--tree text\|dot\|svg`, `--json` |
| `sipl eval FILE` | обчислення терму на стані | `-s "X=2, Y=3"`, `-e/--explain`, `-a/--all-rules`, `-t`, `--max-steps`, `--ascii`, `--json` |
| `sipl visualize FILE` | інтерактивний HTML | `-s`, `-o`, `--open` |
| `sipl analyze FILE` | JSON-звіт (адаптер conformance) | `-s`, `--trace`, `--max-steps` |
| `sipl grammar [FILE]` | показати EBNF / перевірити файл генеричним розпізнавачем | |

Стан задається як `"X=2, Y=3"`, `"X:=2 Y->3"`, `"[X ↦ 2]"` або JSON `'{"X": 2}'`.

## Коди завершення (стабільні)

| Код | Значення |
|---|---|
| 0 | успіх (для `eval`/`analyze` - результат визначений) |
| 1 | лексична або синтаксична помилка в програмі |
| 2 | помилка використання: аргументи, файл, формат стану |
| 3 | `eval`/`analyze`: результат невизначений (⊥) |

## JSON-формати

* `sipl check --json` → `{"ok", "file", "diagnostics": [{code, severity, message, line, column, span, hint?, expected?}], "statements", "variables"}`
* `sipl parse -f json` → вузли `{"type", "id", "span", ...поля..., ...діти...}`
* `sipl term --json` → `{"term", "term_ascii", "term_latex", "tree", "steps"}`
* `sipl eval --json` → `{"status", "initial_state", "final_state", "steps", "undefined"?, "states", "transitions", "trace"}`
* `sipl analyze` → звіт `schema: 1` (див. `conformance/README.md`)
