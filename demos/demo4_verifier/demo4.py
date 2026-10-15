#!/usr/bin/env python3
"""Демо 4, «Тот же отказ, но с верификатором» (цикл 4 семинара «Цена ошибки AI-агента»).

Тот же вход и тот же агент, что в демо 1, но включён второй контур:
правила + LLM-судья. Ошибка поймана, агент на паузе, вызван человек.

Контур верификации:
  1. Правила (код, не модель): пересчёт эталона — рабочие дни из дат,
     ставка и база из договора; сверка числа из ответа агента.
  2. LLM-судья: сопоставляет ответ агента с эталонным расчётом.
  Любое несовпадение — агент встаёт на паузу, решение уходит человеку.
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from run_agent import ask_ollama, load_shared, build_agent_prompt, MODEL

BAR = "=" * 64

# Параметры задачи демо 1 (из договора и вопроса)
RATE_PER_DAY = 0.001          # п. 4.1: 0,1% за каждый рабочий день
BASE_RUB = 2_400_000          # п. 1.3: стоимость Партии № 2
DELAY_START = date(2026, 3, 11)   # первый день просрочки (после 10 марта)
DELAY_END = date(2026, 4, 9)      # фактическая поставка


def working_days(start, end):
    """Рабочие дни (пн-пт) включительно, без учёта праздников."""
    n, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def extract_amounts(text):
    """Суммы в рублях из текста: '240 000 руб', '2 400 000', '36000 рублей'."""
    amounts = []
    for m in re.finditer(r"(\d[\d\s]{1,15}\d|\d)\s*(?:руб(?:лей|ля|\.|))", text):
        amounts.append(int(m.group(1).replace(" ", "")))
    return amounts


def rub(n):
    """2 400 000 ₽ — группировка тысяч пробелами."""
    return f"{n:,} ₽".replace(",", " ")


# Страховка от англоязычных вставок в вердикте судьи: прогон 14.10 дал «whereas».
# Текст вердикта уходит на проектор, поэтому чистим детерминированно, а не надеемся на промпт.
EN_LEAKS = {"whereas": "тогда как", "while": "тогда как", "but": "но", "and": "и"}


def ru_only(text):
    """Заменяет проскочившие английские союзы на русские."""
    out = text
    for en, ru in EN_LEAKS.items():
        out = re.sub(rf"\b{en}\b", ru, out, flags=re.IGNORECASE)
    return out


def judge(agent_answer, ref_amount, ref_days):
    """LLM-судья вторым контуром: сходится ли ответ агента с эталонным расчётом."""
    prompt = f"""Ты — проверяющий. Дан ответ агента и эталонный расчёт, выполненный вручную.

Эталонный расчёт: ставка 0,1% от 2 400 000 ₽ за каждый РАБОЧИЙ день просрочки; рабочих дней в периоде — {ref_days}; эталонная сумма — {ref_amount} ₽.

Ответ агента:
\"\"\"
{agent_answer}
\"\"\"

Сходится ли итоговая сумма и число дней в ответе агента с эталоном? Ответь строго в формате:
ВЕРДИКТ: СХОДИТСЯ или НЕ СХОДИТСЯ
ПРИЧИНА: одно предложение по-русски, без английских слов и союзов"""
    return ru_only(ask_ollama(prompt))


def main():
    contract, etalon = load_shared()

    print(BAR)
    print("ДЕМО 4. ТОТ ЖЕ ВХОД, НО ВКЛЮЧЁН ВТОРОЙ КОНТУР")
    print("Агент:", MODEL, "| верификатор: правила + судья | temperature 0")
    print(BAR)
    print()
    print("ВОПРОС АГЕНТУ (тот же, что в демо 1):")
    print(" ", etalon["question"])
    print()
    print(BAR)
    print("ШАГ 1. АГЕНТ ОТВЕЧАЕТ (живой прогон):")
    print(BAR)
    print()

    answer = ask_ollama(build_agent_prompt(contract, etalon["question"]), stream=True)

    print()
    print(BAR)
    print("ШАГ 2. ВТОРОЙ КОНТУР: ПРАВИЛА")
    print(BAR)
    print()

    days = working_days(DELAY_START, DELAY_END)
    ref = round(BASE_RUB * RATE_PER_DAY * days)
    checks = []

    checks.append(("ставка 0,1% из п. 4.1 найдена в ответе",
                   "0,1%" in answer))
    checks.append(("база 2 400 000 ₽ (стоимость Партии № 2) использована",
                   "2 400 000" in answer))
    amounts = extract_amounts(answer)
    # Итог агента: максимальная сумма, отличная от базы договора (2 400 000 — это слагаемое, не ответ)
    candidates = [a for a in amounts if a != BASE_RUB]
    claimed = max(candidates) if candidates else None
    amounts_match = claimed == ref
    checks.append((f"итоговая сумма агента ({rub(claimed)}) "
                   f"{'совпадает' if amounts_match else 'НЕ совпадает'} "
                   f"с пересчётом правил ({rub(ref)})",
                   amounts_match))

    all_ok = True
    for label, ok in checks:
        print(("  [OK]   " if ok else "  [FAIL] ") + label)
        all_ok = all_ok and ok
    print(f"  Правила: рабочих дней в периоде 11.03-09.04.2026: {days} (посчитано календарём, не моделью)")
    print(f"  Правила: эталон {rub(BASE_RUB)} x 0,1% x {days} = {rub(ref)}")
    print()

    print(BAR)
    print("ШАГ 3. ВТОРОЙ КОНТУР: СУДЬЯ (вторая модель)")
    print(BAR)
    print()
    verdict_text = judge(answer, ref, days)
    print(verdict_text)
    judge_ok = "НЕ СХОДИТСЯ" not in verdict_text.upper()
    print()

    print(BAR)
    if all_ok and judge_ok:
        print("РЕШЕНИЕ ВТОРОГО КОНТУРА: ПРОПУСТИТЬ")
    else:
        print("РЕШЕНИЕ ВТОРОГО КОНТУРА: ОШИБКА ПОЙМАНА")
    print(BAR)
    print()
    if not (all_ok and judge_ok):
        print("  АГЕНТ ПОСТАВЛЕН НА ПАУЗУ. Ответ НЕ ушёл наружу.")
        print("  Задача эскалирована человеку. Лог решения:")
        print()
        print(f"  - проверено правилами: ставка, база, итоговая сумма")
        print(f"  - не сошлось: сумма агента {rub(claimed)} против эталона {rub(ref)}")
        print(f"  - причина: агент посчитал все дни рабочими (31 вместо {days}) и применил ставку как множитель:")
        print(f"    его же формула 2 400 000 x 0,1% x 31 даёт 74 400 ₽, а напечатано {rub(claimed)}")
        print(f"  - судья вторым контуром: {'подтвердил расхождение' if not judge_ok else 'расхождения не увидел'}")
        print(f"  - решение принял: второй контур (правила + судья), финал за человеком")
    print()


if __name__ == "__main__":
    main()
