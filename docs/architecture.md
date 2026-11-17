# Архітектура

```
             grammar/sipl.ebnf ──► sipl.ebnf (генеричний розпізнавач, тести CORE-01)
                    │ (правила)
 текст ──► lexer ──► parser ──► CST (ParseNode) ──► build_ast ──► AST (sipl.ast)
           tokens    рекурсивний   дерево виводу,                  типізовані вузли,
           + spans   спуск         мітки = правила EBNF            id + SourceSpan
                                         │                               │
                                         │                 semantics.builder (⟦·⟧)
                                         │                               ▼
                                         │                   семантичний терм (Term),
                                         │                   кожен вузол має ast_id
                                         │                               │
                                         │                 semantics.evaluator + state
                                         │                               ▼
                                         │               EvalResult: стани, переходи,
                                         │               трейс правил (term_id, ast_id)
                                         ▼                               ▼
                         visualization: text / JSON / DOT / SVG / HTML-ланцюжок (SEM-03)
                                         │
                                cli.py (sipl ...)  ·  api.py (JSON-звіт для conformance)
```

## Модулі (`src/sipl/`)

| Модуль | Призначення | Завдання |
|---|---|---|
| `span.py` | `SourcePos`, `SourceSpan`, `LineIndex` - позиції у вихідному тексті | CORE-02 |
| `diagnostics.py` | `Diagnostic` (код, повідомлення, span, підказка), `SiplSyntaxError` | CORE-02 |
| `lexer.py` | токенізація, синоніми операцій, коментарі, лексичні помилки | CORE-01/02 |
| `ebnf.py` | читання `sipl.ebnf` і точний (переборний) розпізнавач мови | CORE-01 |
| `cst.py` | дерево синтаксичного виводу `ParseNode` | VIS-01 |
| `parser.py` | парсер рекурсивного спуску → CST → AST; діагностики | CORE-02 |
| `ast.py` | типізоване AST: `Program`, `Assign`, `Seq`, `If`, `While`, `Block`, `Skip`, `Num`, `Var`, `BinOp`, `BoolLit`, `Compare`, `Logic`, `Not` | CORE-02 |
| `semantics/terms.py` | модель семантичних термів | SEM-01 |
| `semantics/builder.py` | рекурсивна побудова терму з AST + кроки побудови | SEM-01 |
| `semantics/render.py` | Unicode / ASCII / LaTeX, багаторядковий вивід | SEM-01 |
| `semantics/state.py` | стани, розбір і форматування | SEM-02 |
| `semantics/evaluator.py` | обчислення терму, трейс правил, ⊥ | SEM-02 |
| `visualization/model.py` | єдина деревна модель для CST/AST/терму | VIS-01 |
| `visualization/exporters.py` | text, JSON, DOT, SVG | VIS-01 |
| `visualization/html.py` | інтерактивний ланцюжок рівнів | SEM-03 |
| `api.py` | `analyze_source`, стабільний JSON-звіт | CORE-06 |
| `cli.py` | командний рядок | - |

## Зв'язки між рівнями

* **Код ↔ CST ↔ AST** - через `SourceSpan` (offset/рядок/колонка) кожного вузла.
  Вузол CST відображається на найменший AST-вузол, чий span його містить.
* **AST ↔ терм** - кожен вузол терму зберігає `ast_id`. Для `begin … end` окремого терму
  немає (`⟦begin S end⟧ = ⟦S⟧`), тому `Block` відображається на терм тіла
  (таблиця `astTerm` у HTML).
* **Терм ↔ трейс ↔ стани** - кожен запис трейсу має `term_id`, `ast_id`, номери вхідного
  і вихідного стану; кожен перехід станів посилається на запис трейсу.

## Принципи

* Нуль залежностей під час виконання - встановлюється офлайн, працює на Python ≥ 3.10.
* Граматика - єдине джерело істини: тести перевіряють, що парсер і генеричний
  розпізнавач `sipl.ebnf` приймають одну й ту саму мову.
* Візуалізації не містять логіки мови - лише відображають структури, побудовані бібліотекою.
