# Приклади SIPL

Усі приклади, крім позначених «розширення», написані мовою ядра курсу
(БНФ підручника: `+ - *`, `= >`, `∨ ¬`) і проходять `sipl check --strict`.

| Файл | Що демонструє | Запуск |
|---|---|---|
| `power.sipl` | R = X^Y (приклад практикуму, ПР 1–2) | `sipl eval examples/power.sipl -s "X=5, Y=2" -e` |
| `gcd.sipl` | програма GCD з підручника дослівно (`¬M=N`, `M–N`) | `sipl eval examples/gcd.sipl -s "M=8, N=16" -e` |
| `factorial.sipl` | F = N!, умова `¬(I > N)` | `sipl eval examples/factorial.sipl -s "N=5"` |
| `max.sipl` | розгалуження | `sipl eval examples/max.sipl -s "X=3, Y=7"` |
| `sum_to_n.sipl` | цикл з лічильником | `sipl eval examples/sum_to_n.sipl -s "N=4"` |
| `fibonacci.sipl` | кілька змінних | `sipl eval examples/fibonacci.sipl -s "N=10"` |
| `isqrt.sipl` | вкладені дужки в умові та виразі | `sipl eval examples/isqrt.sipl -s "N=30"` |
| `sign.sipl` | `∨`, `¬`, вкладені `if`, константа `-1` | `sipl eval examples/sign.sipl -s "X=-4"` |
| `divmod.sipl` | приклад МКР; `≥` (розширення `gre`) | `sipl eval examples/divmod.sipl -s "X=7, Y=4"` |
| `div_by_zero.sipl` | ⊥: `div` на нуль (розширення) | `sipl eval examples/div_by_zero.sipl -s "X=1, Y=0" -e -a` |
| `infinite_loop.sipl` | ⊥: цикл не завершується | `sipl eval examples/infinite_loop.sipl --max-steps 200` |
| `syntax_error.sipl` | діагностика з позицією | `sipl check examples/syntax_error.sipl` |
