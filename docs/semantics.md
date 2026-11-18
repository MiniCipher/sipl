# Семантика SIPL: терми та їх обчислення

Реалізовано композиційну семантику курсу (Нікітченко, розд. 1.3; Практикум, ПР 2).
Детальна таблиця «теорія → код → тест» - у [`theory.md`](theory.md).

Стан `st` - скінченна часткова функція `Var → Int`, наприклад `[X ↦ 5, Y ↦ 2]`.
Програма задає біномінативну функцію `State → State`, вираз - номінативну арифметичну
функцію `State → Int`, умова - номінативний предикат `State → Bool`.

## Нотація термів (алгебра A_SIPL)

| Композиція / функція | Запис | ASCII |
|---|---|---|
| присвоєння | `AS^x(fa)` | `AS^x(fa)` |
| послідовне виконання | `fs1 • fs2` (у практикумі `·`) | `fs1 o fs2` |
| умовний оператор | `IF(fb, fs1, fs2)` | так само |
| цикл | `WH(fb, fs)` | так само |
| тотожна функція (`skip`) | `id` | `id` |
| розіменування | `x⇒` | `x=>` |
| константа | `n̄` (`1̅`, `−1̅`) | `#1`, `#-1` |
| суперпозиція | `S²(f, g1, g2)`, `S¹(neg, g)` | `S^2(f, g1, g2)`, `S^1(neg, g)` |

Функції ядра курсу: `add`, `sub`, `mult` (+, –, ∗), `eq`, `gr` (=, >), `or`, `neg` (∨, ¬).
Розширення: `div`, `mod`, `less` (<), `leq` (≤), `neq` (≠), `gre` (≥ - так у практикумі),
`and` (∧), константи `true̅`, `false̅`.

## Побудова терму: правила табл. 1.6

```
sem_P(begin S end)          = sem_S(S)                                NS_Prog
sem_S(x := a)               = AS^x(sem_A(a))                          NS_Stm_As
sem_S(S1; S2)               = sem_S(S1) • sem_S(S2)                   NS_Stm_Seq
sem_S(if b then S1 else S2) = IF(sem_B(b), sem_S(S1), sem_S(S2))      NS_Stm_If
sem_S(while b do S)         = WH(sem_B(b), sem_S(S))                  NS_Stm_Wh
sem_S(begin S end)          = (sem_S(S))                              NS_Stm_BE
sem_S(skip)                 = id                                      NS_Stm_skip
sem_A(n) = n̄                                                          NS_A_Num
sem_A(x) = x⇒                                                         NS_A_Var
sem_A(a1 + a2) = S²(add, sem_A(a1), sem_A(a2))                        NS_A_Add
sem_A(a1 – a2) = S²(sub, sem_A(a1), sem_A(a2))                        NS_A_Sub
sem_A(a1 ∗ a2) = S²(mult, sem_A(a1), sem_A(a2))                       NS_A_Mult
sem_A((a))     = sem_A(a)                                             NS_A_Par
sem_B(a1 = a2) = S²(eq, sem_A(a1), sem_A(a2))                         NS_B_eq
sem_B(a1 > a2) = S²(gr, sem_A(a1), sem_A(a2))                         NS_B_gr
sem_B(b1 ∨ b2) = S²(or, sem_B(b1), sem_B(b2))                         NS_B_or
sem_B(¬b)      = S¹(neg, sem_B(b))                                    NS_B_neg
sem_B((b))     = sem_B(b)                                             NS_B_Par
```

`sipl term FILE --steps` друкує застосування правил у порядку розв'язку ПР 2 (зверху вниз),
кожне - як конкретне правило:

```
  1. NS_Prog: sem_P(begin R := 1; while Y > 0 do …) = sem_S(R := 1; while Y > 0 do …)
  2. NS_Stm_Seq: sem_S(R := 1; while …) = sem_S(R := 1) • sem_S(while …)
  3. NS_Stm_As: sem_S(R := 1) = AS^R(sem_A(1))
  4. NS_A_Num: sem_A(1) = 1̅
  5. NS_Stm_Wh: sem_S(while Y > 0 do …) = WH(sem_B(Y > 0), sem_S(begin … end))
  6. NS_B_gr: sem_B(Y > 0) = S²(gr, sem_A(Y), sem_A(0))
  …
Семантичний терм програми:
AS^R(1̅) • WH(S²(gr, Y⇒, 0̅), AS^R(S²(mult, R⇒, X⇒)) • AS^Y(S²(sub, Y⇒, 1̅)))
```

Композиція `•` асоціативна, тому `(P1 • P2) • P3` друкується як `P1 • P2 • P3`.

## Обчислення терму: формули табл. 1.5

| Формула | Зміст |
|---|---|
| `AF_S` | `(Sⁿ(f, g1, …, gn))(st) = f(g1(st), …, gn(st))` |
| `AF_AS` | `ASˣ(fa)(st) = st ∇ [x ↦ fa(st)]` |
| `AF_SEQ` | `(fs1 • fs2)(st) = fs2(fs1(st))` |
| `AF_IF` | `IF(fb, fs1, fs2)(st) = fs1(st)`, якщо `fb(st) = true`; `fs2(st)`, якщо `fb(st) = false` |
| `AF_WH` | `WH(fb, fs)(st) = stₙ`, де `st₀ = st`, `stₖ₊₁ = fs(stₖ)`, `fb(st₀) = … = fb(stₙ₋₁) = true`, `fb(stₙ) = false` |
| `AF_DNM` | `x⇒(st) = st(x)` |
| `AF_ID` | `id(st) = st` |
| `AF_CONST` | `n̄(st) = n` (функція-константа, розд. 1.3.1) |

Приклад трейсу (`sipl eval examples/power.sipl -s "X=5, Y=2" -e -a`):

```
[AF_AS]  AS^R(1̅)(st0) = st0 ∇ [R ↦ 1̅(st0)] = st0 ∇ [R ↦ 1] = [X ↦ 5, Y ↦ 2, R ↦ 1] = st1
[AF_WH]  ітерація 1: fb(st0′) = S²(gr, Y⇒, 0̅)(st1) = true ⇒ st1′ = fs(st0′) = fs(st1) = st3
  [AF_S]   S²(gr, Y⇒, 0̅)(st1) = gr(Y⇒(st1), 0̅(st1)) = gr(2, 0) = true
    [AF_DNM] Y⇒(st1) = st1(Y) = 2
…
[AF_WH]  fb(st2′) = S²(gr, Y⇒, 0̅)(st5) = false ⇒ цикл завершено, n = NumItWH = 2
```

Номери станів `st0, st1, …` у трейсі глобальні (кожне присвоєння створює новий стан);
`st0′, st1′, …` - стани `st₀, st₁, …` з формули AF_WH для конкретного циклу.

## Частковість (Зауваження 1.6)

> Якщо значення однієї з функцій, що фігурує у формулі, не є визначеним, то і результат не
> буде визначеним.

Тому семантика **строга**: усі аргументи суперпозиції обчислюються, і невизначеність будь-якого з
них робить невизначеним результат - зокрема `S²(or, ⊥, true)` невизначене.

Причини невизначеності (`⊥`):

* `UNBOUND` - `x⇒(st)`, коли `x` не має значення в `st`;
* `DIV_ZERO` - `div` або `mod` на 0 (лише в розширенні);
* `STEP_LIMIT` - цикл не завершився за задану кількість застосувань формул (`--max-steps`,
  типово 10 000).

За підручником, якщо цикл не завершується, `NumItWH` і значення `WH` невизначені. Завершуваність
алгоритмічно нерозв'язна, тому інструмент **не вирішує** її: ліміт кроків - інженерне наближення,
і `STEP_LIMIT` означає «за N кроків результат не отримано».

## Розширення

`div` і `mod` - ціла частка й остача з округленням вниз (`x = y·div(x, y) + mod(x, y)`,
`-7 div 2 = -4`, `-7 mod 2 = 1`). Для натуральних аргументів, як у задачах практикуму, це
звичайне ділення націло.
