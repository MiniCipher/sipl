# Відповідність теорії курсу

Джерела:
* **[Н]** Нікітченко М.С. Теорія програмування. - К.: КНУ ім. Т. Шевченка, 2020. Розділ 1.2–1.3 (с. 6–21).
* **[П]** Теорія програмування. Практикум: ПР 1 «Синтаксис програм», ПР 2 «Семантика програм.
  Семантичні терми», приклад МКР 1.

Кожен пункт нижче перевірено тестами (вказано файл).

## Синтаксис

| Теорія | Де в коді | Тест |
|---|---|---|
| БНФ SIPL, табл. 1.4 [Н, с. 10]: `P ::= begin S end`, `S`, `a`, `b`, `x`, `n` | `grammar/sipl.ebnf` (ядро курсу) | `test_grammar.py::test_core_grammar_is_the_course_bnf` - множина терміналів збігається з БНФ |
| `n ::= … –1 \| 0 \| 1 …` - від'ємні числа | правило `number = ["-"], NUMBER` | `test_parser.py::test_negative_numbers` |
| Пріоритети [Н, с. 9–10]: `*`; `+ –`; `= >`; `¬`; `∨`; `:=`; `while`; `if`; `;` | стратифікація правил (`aexpr`/`term`, `bexpr`/`bfactor`, гілки `if` і тіло `while` - один оператор) | `test_parser.py::test_ast_shapes`, conformance `if-then-seq-priority`, `neg-binds-weaker-than-eq` |
| Усі бінарні операції лівоасоціативні [Н, с. 10] | ліві згортки `_fold_arith`, `_fold_logic`, `_build_stmt_seq` | conformance `seq-left-assoc`, `sub-left-assoc` |
| «Друга можливість досягти однозначності - ввести нові метасимволи» [Н, с. 10] | `sipl.ebnf` - саме така однозначна форма БНФ | `test_grammar.py` (генеричний розпізнавач ≡ парсер) |
| Дерево синтаксичного виводу, перевірка правильності обходом листків [П, ПР 1] | `visualization/derivation.py`, `sipl tree` | `test_visualization.py::test_course_derivation_tree_as_in_practical_work_1` - ті самі 24 листки, що на рис. 1 практикуму |
| Програма GCD [Н, приклад 1.3] (`¬M=N`, `M–N`) | лексер приймає `–`, `∗`, `¬`, `∨` | `test_parser.py::test_textbook_gcd_program` |

### Розширення

У БНФ курсу немає `<`, `≤`, `≠`, `≥`, `∧`, `true`/`false`, `div`, `mod`, але задачі практикуму
їх використовують (МКР: `while X ≥ Y` → `S²(gre, X⇒, Y⇒)`; варіанти «використовуючи функції div,
mod»). Вони описані окремо (`grammar/sipl-ext.ebnf`), за замовчуванням приймаються з
попередженням `W201`, а з `--strict` відхиляються помилкою `E201`. Правила побудови термів для них
утворені за тією ж схемою, що й у табл. 1.6, і позначені як розширення.

## Дані та функції [Н, 1.3.1–1.3.2]

| Теорія | Де в коді |
|---|---|
| `Int`, `Bool = {true, false}`, `State = Var → Int` | `semantics/state.py` (стан - `dict[str, int]`), значення `true`/`false` |
| Накладання `∇`: `[M↦8, N↦16] ∇ [M↦3, X↦4] = [M↦3, N↦16, X↦4]` | `AF_AS` у `evaluator.py` | 
| Розіменування `x⇒` - часткова функція (не визначена, якщо `x` не має значення) | `AF_DNM`, код `UNBOUND` |
| Константа `n̄(st) = n` | `ConstT`, формула `AF_CONST` |
| Операції `add, sub, mult, or, neg, eq, gr` | `terms.OP_NAMES`; у термах - саме ці імена: `S²(add, …)` |

Тест: `test_evaluator.py::test_overlay_keeps_order`.

## Композиції та формули обчислення, табл. 1.5

| Формула | Реалізація |
|---|---|
| `AF_S`: `(Sⁿ(f, g1,…,gn))(st) = f(g1(st),…,gn(st))` | `Evaluator._eval_body`; пояснення: `S²(gr, Y⇒, 0̄)(st0) = gr(Y⇒(st0), 0̄(st0)) = gr(2, 0) = true` - як у ПР 2 |
| `AF_AS`: `ASˣ(fa)(st) = st ∇ [x ↦ fa(st)]` | `AF_AS`: `ASᴿ(1̄)(st0) = st0 ∇ [R ↦ 1̄(st0)] = st0 ∇ [R ↦ 1] = …` |
| `AF_SEQ`: `(fs1 • fs2)(st) = fs2(fs1(st))` | `AF_SEQ` |
| `AF_IF` | `AF_IF`, у трейсі `fb = true` / `fb = false` |
| `AF_WH`: `WH(fb,fs)(st) = stₙ`, `st₀ = st`, `stₖ₊₁ = fs(stₖ)`, `fb(st₀..stₙ₋₁) = true`, `fb(stₙ) = false` | `_exec_while`: послідовність `st0′, st1′, …`, кількість ітерацій `NumItWH` |
| `AF_DNM`, `AF_ID` | `AF_DNM`, `AF_ID` |
| **Зауваження 1.6** - частковість: якщо значення будь-якої функції у формулі не визначене, результат не визначений | строга семантика всіх суперпозицій, зокрема `or`: `S²(or, ⊥, true)` не визначене |
| «Якщо цикл не завершується, то NumItWH … невизначеним» | ліміт кроків → `⊥` з кодом `STEP_LIMIT` (завершуваність алгоритмічно нерозв'язна, тому це інженерне наближення) |

Тести: `test_evaluator.py::test_practicum_power_x5_y2` (R = 25 на `[X↦5, Y↦2]`, як у ПР 2),
`test_textbook_example_1_4_gcd` (`[M↦8, N↦16]` → `[M↦8, N↦8]`), `test_strict_partiality`.

## Побудова семантичного терму, табл. 1.6

| Правило | Реалізація (`semantics/builder.py`) |
|---|---|
| `NS_Prog`, `NS_Stm_As`, `NS_Stm_Seq`, `NS_Stm_If`, `NS_Stm_Wh`, `NS_Stm_BE`, `NS_Stm_skip` | `TermBuilder._rule` / `_build` |
| `NS_A_Num`, `NS_A_Var`, `NS_A_Add`, `NS_A_Sub`, `NS_A_Mult`, `NS_A_Par` | те саме; дужки - окремі кроки `NS_A_Par` |
| `NS_B_eq`, `NS_B_gr`, `NS_B_or`, `NS_B_neg`, `NS_B_Par` | те саме |
| Процес: «вибір правила → уніфікатор → конкретне правило → заміна» [Н, с. 19–20] | кожен крок містить конкретне правило `lhs = rhs`, напр. `sem_S(R := 1) = AS^R(sem_A(1))` |

Порядок кроків - зверху вниз, як у розв'язку ПР 2: `NS_Prog`, `NS_Stm_Seq`, `NS_Stm_As`,
`NS_A_Num`, `NS_Stm_Wh`, `NS_B_gr`, … (`test_terms.py::test_construction_steps_follow_the_practicum`).

Еталонні терми, які відтворюються дослівно:

| Джерело | Терм |
|---|---|
| [Н] приклад 1.2, `X+Y*Z` | `S²(add, X⇒, S²(mult, Y⇒, Z⇒))` |
| [Н] приклад 1.3, GCD | `WH(S¹(neg, S²(eq, M⇒, N⇒)), IF(S²(gr, M⇒, N⇒), ASᴹ(S²(sub, M⇒, N⇒)), ASᴺ(S²(sub, N⇒, M⇒))))` |
| [П] ПР 2, xʸ | `ASᴿ(1̄) • WH(S²(gr, Y⇒, 0̄), ASᴿ(S²(mult, R⇒, X⇒)) • ASʸ(S²(sub, Y⇒, 1̄)))` |
| [П] МКР, x ÷ y | `ASᴿ(0̄) • WH(S²(gre, X⇒, Y⇒), ASˣ(S²(sub, X⇒, Y⇒)) • ASᴿ(S²(add, R⇒, 1̄)))` |

## Нотація

| Підручник / практикум | Вивід програми (Unicode) | ASCII | LaTeX |
|---|---|---|---|
| `ASˣ(…)` | `AS^X(…)` | `AS^X(…)` | `\mathrm{AS}^{X}(…)` |
| `•` [Н], `·` [П] | `•` | `o` | `\bullet` |
| `n̄` (константа з рискою) | `1̅` | `#1` | `\overline{1}` |
| `X⇒` | `X⇒` | `X=>` | `X\Rightarrow` |
| `S²(add, …)`, `S¹(neg, …)` | так само | `S^2(add, …)` | `S^{2}(\mathit{add}, …)` |
| `[X ↦ 5]` | `[X ↦ 5]` | `[X -> 5]` | - |
