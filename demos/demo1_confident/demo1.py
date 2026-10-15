#!/usr/bin/env python3
"""Демо 1, «Уверенный ответ» (цикл 1 семинара «Цена ошибки AI-агента»).

Агент получает синтетический договор и вопрос с проверяемым числовым ответом.
Отвечает быстро, гладко, уверенно и НЕВЕРНО, причём дважды: (1) считает все дни
подряд рабочими, хотя п. 4.1 начисляет неустойку только за рабочие дни;
(2) цифры не воспроизводят его же формулу — 2 400 000 x 0,1% x 31 = 74 400 руб.,
а в ответе напечатано 240 000 руб. (ставка применена как множитель 0,1).

Ход прогона: вопрос, ответ агента (стриминг), пауза на Enter,
затем раскрывается эталон с расчётом.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from run_agent import ask_ollama, load_shared, build_agent_prompt, MODEL

BAR = "=" * 64


def main():
    contract, etalon = load_shared()

    print(BAR)
    print("ДЕМО 1. УВЕРЕННЫЙ ОТВЕТ")
    print("Агент: локальная модель", MODEL, "| temperature 0 | офлайн")
    print(BAR)
    print()
    print("ДОКУМЕНТ: Договор поставки № 17-Т/2026 (синтетический)")
    print()
    print("ВОПРОС АГЕНТУ:")
    print(" ", etalon["question"])
    print()
    print(BAR)
    print("ОТВЕТ АГЕНТА (живой прогон):")
    print(BAR)
    print()

    answer = ask_ollama(build_agent_prompt(contract, etalon["question"]), stream=True)

    print()
    print(BAR)
    input("Нажмите Enter, чтобы показать эталон...")
    print()

    correct = etalon["correct"]
    print(BAR)
    print("ЭТАЛОН (посчитан вручную, не моделью):")
    print(BAR)
    print()
    print(f"  Правильный ответ: {correct['answer_rub']:,} ₽".replace(",", " "))
    print(f"  Основание: {correct['clause']}")
    print()
    print("  Расчёт эталона:")
    print("   ", correct["reasoning"])
    print()
    print("  Ошибка агента двойная:")
    print("   1) взят не тот период: все дни подряд посчитаны рабочими,")
    print("      а п. 4.1 начисляет неустойку только за РАБОЧИЕ дни (31 против 22);")
    print("   2) цифры не воспроизводят его же формулу:")
    print("      2 400 000 x 0,1% x 31 = 74 400 руб., а напечатано 240 000 руб.")
    print("  Оба дефекта оформлены как чистый правильный ответ:")
    print("  именно такие ошибки проходят ревью.")
    print()


if __name__ == "__main__":
    main()
