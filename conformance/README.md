# SIPL Conformance Suite (CORE-06)

Набір програм SIPL з очікуваними результатами, який можна запускати проти **будь-якої**
реалізації SIPL. Runner `run_conformance.py` використовує лише стандартну бібліотеку Python
і не імпортує пакет `sipl`: з реалізацією він спілкується через командний рядок.

```bash
python conformance/run_conformance.py                         # перевіряє `sipl analyze`
python conformance/run_conformance.py --impl "python -m sipl analyze" -v
python conformance/run_conformance.py --impl "node my-sipl.js analyze"   # інша реалізація
python conformance/run_conformance.py --filter power          # лише кейси з 'power' у назві
python conformance/run_conformance.py --json report.json      # машинозчитуваний звіт
```

Код завершення runner'а: `0` - усі кейси пройдено, `1` - є провали, `2` - не знайдено кейсів.

## Формат кейсу

Кожен кейс - два файли з однаковою назвою в `cases/`:

* `NNN-name.sipl` - програма;
* `NNN-name.expect.json` - очікування (JSON Schema: [`schema.json`](schema.json)).

```json
{
  "description": "power",
  "category": "semantics",
  "syntax": "ok",
  "ast": "(block (seq (assign R (num 1)) (while ...)))",
  "term": "AS^R(#1) o WH(S^2(>, Y=>, #0), ...)",
  "runs": [
    {"state": {"X": 2, "Y": 3}, "result": "defined", "final_state": {"X": 2, "Y": 0, "R": 8}},
    {"state": {}, "result": "undefined", "undefined_code": "UNBOUND"}
  ]
}
```

| Поле | Обов'язкове | Зміст |
|---|---|---|
| `category` | так | `semantics`, `undefined` або `syntax-error` |
| `syntax` | так | `ok` - програма коректна, `error` - має бути відхилена |
| `error` | для `syntax: error` | `{"line": L, "column": C}` - позиція першої помилки (1-based) |
| `ast` | ні | канонічне S-вираз-представлення AST (див. нижче) |
| `term` | ні | семантичний терм в ASCII-нотації (пробіли ігноруються) |
| `runs[]` | ні | запуски: початковий `state`, очікуваний `result` (`defined`/`undefined`), `final_state` для `defined`; необов'язкові `undefined_code` і `max_steps` |

**Порівняння.** AST порівнюється після нормалізації пробілів; терм - без пробілів; стан -
як JSON-об'єкт (порядок ключів неважливий); позиція помилки - за рядком і колонкою.
`undefined_code` перевіряється, лише якщо вказаний.

### Канонічне AST (S-вирази)

```
(assign X e)  (seq S1 S2)  (if b S1 S2)  (while b S)  (block S)  (skip)
(num n)  (var x)  (+ e1 e2) (- ...) (* ...) (/ ...)
(true) (false)  (< e1 e2) (<= ...) (= ...) (<> ...) (> ...) (>= ...)
(and b1 b2)  (or b1 b2)  (not b)
```
`;` лівоасоціативна: `A; B; C` = `(seq (seq A B) C)`. Дужки у виразах в AST не зберігаються.

### ASCII-нотація терму

`AS^x(..)`, композиція ` o `, `IF(b, P1, P2)`, `WH(b, P)`, `id`, розіменування `x=>`,
константи `#5`, `#T`, `#F`, суперпозиції `S^2(op, a, b)` / `S^1(not, b)`, де `op` ∈
`+ - * / < <= = <> > >= and or`.

## Протокол адаптера

Runner викликає `<impl> FILE` (синтаксис, AST, терм) і
`<impl> FILE --state '<json>' [--max-steps N]` (для кожного запуску) та очікує в stdout
JSON-об'єкт:

```json
{
  "syntax_ok": true,
  "diagnostics": [{"line": 2, "column": 8, "message": "..."}],
  "ast": "(...)",
  "term": "...",
  "result": {
    "status": "defined",
    "final_state": {"X": 2},
    "undefined": {"code": "DIV_ZERO", "reason": "..."}
  }
}
```

`result` - `null`, якщо стан не передано. Коди невизначеності цієї реалізації:
`UNBOUND` (змінна без значення), `DIV_ZERO`, `UNDEFINED_CONDITION`, `STEP_LIMIT`.

## Склад набору

* 25 кейсів `semantics` - усі оператори, пріоритети й асоціативність, дужки, коментарі,
  Unicode-операції, вкладені цикли й розгалуження;
* 7 кейсів `undefined` - незв'язана змінна, ділення на нуль, нескінченний цикл, логіка Кліні;
* 22 кейси `syntax-error` - лексичні та синтаксичні помилки з точною позицією.
