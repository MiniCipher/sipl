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
  "description": "power practicum",
  "category": "semantics",
  "language": "core",
  "syntax": "ok",
  "ast": "(seq (assign R (num 1)) (while (> (var Y) (num 0)) (block ...)))",
  "term": "AS^R(#1) o WH(S^2(gr, Y=>, #0), AS^R(S^2(mult, R=>, X=>)) o AS^Y(S^2(sub, Y=>, #1)))",
  "runs": [
    {"state": {"X": 5, "Y": 2}, "result": "defined", "final_state": {"X": 5, "Y": 0, "R": 25}},
    {"state": {}, "result": "undefined", "undefined_code": "UNBOUND"}
  ]
}
```

| Поле | Обов'язкове | Зміст |
|---|---|---|
| `category` | так | `semantics`, `undefined` або `syntax-error` |
| `language` | ні | `core` - програма мови ядра курсу (має прийматися з `--strict`), `extension` - використовує розширення (з `--strict` має відхилятися) |
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
Програма `begin S end` подається як S-вираз її тіла `S` (`sem_P(begin S end) = sem_S(S)`).
`;` лівоасоціативна: `A; B; C` = `(seq (seq A B) C)`. Дужки у виразах у S-виразі не показуються.
`div` записується як `/`. Від'ємна константа - `(num -1)`.

### ASCII-нотація терму

`AS^x(..)`, композиція ` o ` (у підручнику `•`), `IF(b, P1, P2)`, `WH(b, P)`, `id`,
розіменування `x=>`, константи `#5`, `#-1`, `#true`, `#false`, суперпозиції `S^2(f, a, b)` /
`S^1(neg, b)`, де `f` - ім'я функції алгебри: `add sub mult eq gr or neg` (ядро курсу) та
`div mod less leq neq gre and` (розширення).

## Протокол адаптера

Runner викликає `<impl> FILE` (синтаксис, AST, терм), `<impl> FILE --strict` (лише для кейсів
з полем `language`: перевірка мови ядра курсу) і `<impl> FILE --state '<json>' [--max-steps N]`
(для кожного запуску) та очікує в stdout JSON-об'єкт:

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
`UNBOUND` (розіменування змінної без значення), `DIV_ZERO` (`div`/`mod` на 0), `STEP_LIMIT`.

## Склад набору

* 28 кейсів `semantics` - усі конструкції БНФ курсу, приклади підручника (1.2 X+Y*Z, GCD) і
  практикуму (степінь, МКР), пріоритети й асоціативність, дужки, від'ємні константи,
  типографські варіанти символів (`–`, `∗`), коментарі; 4 з них - розширення практикуму;
* 7 кейсів `undefined` - строга частковість (Зауваження 1.6, зокрема для `∨`), незавершений
  цикл, ділення на нуль;
* 24 кейси `syntax-error` - лексичні та синтаксичні помилки з точною позицією.
