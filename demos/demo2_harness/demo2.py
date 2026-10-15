"""Демо 2 «Харнесс в прямом эфире»: прогон eval-харнесса по golden set.

Сценарий: сначала дружелюбный датасет (высокий pass rate), затем честный
(тот же набор задач, но без подсказок в вопросе) — видно, как «95% accuracy»
превращается в другую цифру на честных формулировках.

Извлечение ответа: regex по суммам в рублях, допуск к эталону ±1%.
Классификация FAIL — демо-эвристики по числам в ответе (см. README):
  «инструкция» — модель не дала числа в рублях;
  «факт»       — число сходится с расчётом по НЕВЕРНЫМ вводным из договора
                 (сумма другой партии или другая ставка);
  «рассуждение» — число сходится с расчётом по календарным дням или не сходится
                 ни с чем (арифметика, период, прочее);
  «инструмент» — в этом демо не участвует (агент без инструментов), показываем 0.

Запуск: python3 demo2.py [--n 6] [--full] [--dataset friendly|honest|both]
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "shared"))
from run_agent import ask_ollama, build_agent_prompt, MODEL  # noqa: E402

TOLERANCE = 0.01  # допуск к эталону ±1%

# число перед рублёвым маркером: "52 800 руб", "52800 рублей", "52 800,00 ₽"
RUB_RE = re.compile(
    r"(\d[\d\s  ]*(?:[.,]\d+)?)\s*(?:руб(?:лей|ля|ль)?|₽|RUB)",
    re.IGNORECASE)


def extract_rub_amounts(text):
    """Все суммы в рублях из ответа, в порядке появления."""
    amounts = []
    for m in RUB_RE.finditer(text):
        raw = m.group(1)
        digits = re.sub(r"[\s  ]", "", raw).replace(",", ".")
        try:
            amounts.append(float(digits))
        except ValueError:
            continue
    return amounts


def close(x, ref):
    return ref != 0 and abs(x - ref) <= TOLERANCE * ref


def classify_failure(task, amounts):
    """Эвристическая классификация ошибки по числам в ответе."""
    if not amounts:
        return "инструкция"

    rate = task["rate_pct"] / 100
    amount = task["amount_rub"]
    wd = task["working_days"]
    cal = task["calendar_days"]
    other_amount = task["other_party_amount_rub"]

    wrong_rate_variants = [r / 100 for r in (0.05, 0.1, 0.2) if r != task["rate_pct"]]

    for a in amounts:
        if close(a, amount * rate * cal):
            return "рассуждение"  # период: календарные дни вместо рабочих
    for a in amounts:
        if close(a, other_amount * rate * wd) or close(a, other_amount * rate * cal):
            return "факт"  # сумма другой партии
        if any(close(a, amount * r * wd) or close(a, amount * r * cal)
               for r in wrong_rate_variants):
            return "факт"  # не та ставка
    return "рассуждение"  # арифметика / иной неверный расчёт


def run_dataset(name, tasks, n, model):
    print()
    print("=" * 64)
    print(f"  ДАТАСЕТ: {name}, задач в прогоне: {min(n, len(tasks))}")
    print("=" * 64)

    results = []
    t0 = time.monotonic()
    for i, task in enumerate(tasks[:n], 1):
        print(f"\nЗадача {i}/{min(n, len(tasks))} ({task['id']}): запрос к модели...", flush=True)
        prompt = build_agent_prompt(task["contract_variant"], task["question"])
        t_start = time.monotonic()
        try:
            # num_predict — защита от зацикливания; таймаут — защита прогона от зависания
            response = ask_ollama(prompt, model=model, timeout=180, num_predict=800)
        except Exception as e:
            response = None
            print(f"  (модель не ответила: {type(e).__name__})")
        elapsed = time.monotonic() - t_start

        amounts = extract_rub_amounts(response or "")
        final = amounts[-1] if amounts else None
        passed = final is not None and close(final, task["answer_rub"])

        if passed:
            verdict = "PASS"
            err_class = None
            detail = f"ответ {fmt(int(final))} руб, эталон {fmt(int(task['answer_rub']))} руб"
        else:
            verdict = "FAIL"
            err_class = classify_failure(task, amounts)
            got = f"ответ {fmt(int(final))} руб" if final is not None else "число в рублях не найдено"
            detail = f"{got}, эталон {fmt(int(task['answer_rub']))} руб, класс ошибки: {err_class}"

        print(f"[{verdict}] {task['id']}: {detail} ({elapsed:.1f} с)")
        results.append({"id": task["id"], "passed": passed, "err_class": err_class})

    total_time = time.monotonic() - t0
    n_pass = sum(1 for r in results if r["passed"])
    n_run = len(results)
    rate_pct = round(100 * n_pass / n_run) if n_run else 0

    classes = {"факт": 0, "инструкция": 0, "рассуждение": 0, "инструмент": 0}
    for r in results:
        if not r["passed"]:
            classes[r["err_class"]] += 1

    print()
    print("-" * 64)
    print(f"  ИТОГ ПО ДАТАСЕТУ «{name}»")
    print("-" * 64)
    print(f"  PASS RATE: {rate_pct}% ({n_pass} из {n_run})")
    print(f"  Время прогона: {total_time:.0f} с")
    print("  Ошибки по классам:")
    print(f"    факт:        {classes['факт']}")
    print(f"    инструкция:  {classes['инструкция']}")
    print(f"    рассуждение: {classes['рассуждение']}")
    print(f"    инструмент:  {classes['инструмент']} (в этом демо агент без инструментов)")
    return {"name": name, "pass_rate": rate_pct, "n_pass": n_pass, "n_run": n_run,
            "classes": classes, "time_s": total_time}


def fmt(n):
    return f"{n:,}".replace(",", " ")


def load_tasks(path):
    return json.loads(path.read_text(encoding="utf-8"))["tasks"]


def main():
    parser = argparse.ArgumentParser(description="Демо 2: прогон eval-харнесса")
    parser.add_argument("--n", type=int, default=6,
                        help="задач на датасет (по умолчанию 6, короткий прогон на 2-3 минуты)")
    parser.add_argument("--full", action="store_true",
                        help="полный прогон: все 15 задач каждого датасета")
    parser.add_argument("--dataset", choices=["friendly", "honest", "both"], default="both")
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()

    n = 15 if args.full else args.n

    print("ДЕМО 2: ХАРНЕСС В ПРЯМОМ ЭФИРЕ")
    print(f"Модель: {args.model} (temperature 0)")
    print("Один и тот же golden set, два датасета: дружелюбный и честный.")

    summaries = []
    if args.dataset in ("friendly", "both"):
        summaries.append(run_dataset(
            "ДРУЖЕЛЮБНЫЙ (подсказки в вопросе)",
            load_tasks(HERE / "dataset_friendly.json"), n, args.model))
    if args.dataset in ("honest", "both"):
        summaries.append(run_dataset(
            "ЧЕСТНЫЙ (только даты, без подсказок)",
            load_tasks(HERE / "dataset_honest.json"), n, args.model))

    if len(summaries) == 2:
        print()
        print("#" * 64)
        print("  СВОДКА")
        print("#" * 64)
        f, h = summaries
        print(f"  Дружелюбный датасет:  PASS RATE {f['pass_rate']}% ({f['n_pass']} из {f['n_run']})")
        print(f"  Честный датасет:      PASS RATE {h['pass_rate']}% ({h['n_pass']} из {h['n_run']})")
        print("  Те же задачи, та же модель, тот же харнесс.")
        print("  Разница — только в формулировке вопроса.")


if __name__ == "__main__":
    main()
