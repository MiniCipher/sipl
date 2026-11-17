# Приклади SIPL

| Файл | Що демонструє | Запуск |
|---|---|---|
| `power.sipl` | R = X^Y (з постановки) | `sipl eval examples/power.sipl -s "X=2, Y=3" -e` |
| `factorial.sipl` | F = N! | `sipl eval examples/factorial.sipl -s "N=5"` |
| `gcd.sipl` | НСД відніманням, вкладений if у while | `sipl eval examples/gcd.sipl -s "X=12, Y=18" -e` |
| `max.sipl` | розгалуження | `sipl eval examples/max.sipl -s "X=3, Y=7"` |
| `sum_to_n.sipl` | цикл з лічильником | `sipl eval examples/sum_to_n.sipl -s "N=4"` |
| `divmod.sipl` | умова з `and` | `sipl eval examples/divmod.sipl -s "X=17, Y=5"` |
| `fibonacci.sipl` | кілька змінних | `sipl eval examples/fibonacci.sipl -s "N=10"` |
| `isqrt.sipl` | дужки в арифметиці та умові | `sipl eval examples/isqrt.sipl -s "N=30"` |
| `sign.sipl` | `or`, `and`, `not`, вкладені `if` | `sipl eval examples/sign.sipl -s "X=-4"` |
| `div_by_zero.sipl` | ⊥: ділення на нуль | `sipl eval examples/div_by_zero.sipl -s "X=1, Y=0" -e` |
| `infinite_loop.sipl` | ⊥: ліміт кроків | `sipl eval examples/infinite_loop.sipl --max-steps 200` |
| `syntax_error.sipl` | діагностика з позицією | `sipl check examples/syntax_error.sipl` |
