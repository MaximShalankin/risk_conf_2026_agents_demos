"""Генератор датасетов демо 2 «Харнесс в прямом эфире» (Risk Conference).

Два датасета из одних и тех же 15 задач (расчёт неустойки по договору поставки):
- dataset_friendly.json: в вопросе готовое число рабочих дней и прямая отсылка к п. 4.1,
  модели остаётся только умножение (ожидаем высокий pass rate).
- dataset_honest.json: в вопросе только даты, без намёка на рабочие дни,
  модель сама считает период (ожидаем провал на ловушке «календарные vs рабочие»).

Эталон (answer_rub) считается только кодом: рабочие дни пн-пт, без праздников,
со дня после дедлайна по день фактической поставки включительно.

Запуск: python3 generate_datasets.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261015
N_TASKS = 15

RATES = [
    (0.05, "0,05%", "ноль целых пять сотых процента"),
    (0.1, "0,1%", "ноль целых одна десятая процента"),
    (0.2, "0,2%", "ноль целых две десятых процента"),
]

AMOUNTS = [1_200_000, 1_600_000, 1_800_000, 2_400_000, 2_800_000,
           3_200_000, 3_600_000, 4_200_000, 4_800_000]

PARTIES = [
    ("ТехноСнаб", "ДатаЛайн"),
    ("Вектор Поставка", "НордСофт"),
    ("АльфаКомплект", "Сфера Дата"),
    ("ПромРесурс", "КвантСистемы"),
]

MONTHS_RU = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
             "июля", "августа", "сентября", "октября", "ноября", "декабря"]

TRAP_CLASS = "calendar_vs_working_days"


def date_ru(d):
    return f"{d.day} {MONTHS_RU[d.month]} {d.year} г."


def fmt_amount(n):
    return f"{n:,}".replace(",", " ")


def plural_days(n):
    if 11 <= n % 100 <= 14:
        return "рабочих дней"
    tail = n % 10
    if tail == 1:
        return "рабочий день"
    if 2 <= tail <= 4:
        return "рабочих дня"
    return "рабочих дней"


def working_days_between(deadline, actual):
    """Рабочие дни (пн-пт) со дня после дедлайна по день поставки включительно."""
    count = 0
    d = deadline + timedelta(days=1)
    while d <= actual:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count


def nearest_workday(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


CONTRACT_TEMPLATE = """# ДОГОВОР ПОСТАВКИ № {doc_no}-Т/2026

г. Москва, {doc_date}

Общество с ограниченной ответственностью «{supplier}» (далее — Поставщик) и общество с ограниченной ответственностью «{buyer}» (далее — Покупатель) заключили настоящий Договор о нижеследующем.

## 1. Предмет договора

1.1. Поставщик обязуется поставить Покупателю серверное оборудование (далее — Оборудование) двумя партиями, а Покупатель обязуется принять и оплатить его.

1.2. Партия № 1: стоимость {amount1_str} рублей, срок поставки — не позднее {deadline1_ru}.

1.3. Партия № 2: стоимость {amount2_str} рублей, срок поставки — не позднее {deadline2_ru}.

## 2. Приёмка

2.1. Покупатель проводит приёмку Оборудования в течение 5 (пяти) рабочих дней с даты поставки.

2.2. Претензии по качеству Оборудования предъявляются в течение 10 (десяти) рабочих дней с даты подписания акта приёмки.

## 3. Порядок расчётов

3.1. Покупатель уплачивает аванс в размере 30% от стоимости каждой Партии в течение 5 (пяти) рабочих дней с даты подписания Договора.

3.2. Оставшиеся 70% уплачиваются в течение 15 (пятнадцати) календарных дней с даты подписания акта приёмки соответствующей Партии.

## 4. Ответственность сторон

4.1. За нарушение срока поставки Оборудования Поставщик уплачивает Покупателю неустойку в размере {rate_str} ({rate_words}) от стоимости непоставленной в срок Партии за каждый рабочий день просрочки.

4.2. Уплата неустойки не освобождает Поставщика от исполнения обязательств по Договору.

4.3. Покупатель вправе требовать возмещения убытков в части, не покрытой неустойкой.

4.4. За нарушение Покупателем сроков оплаты Покупатель уплачивает Поставщику неустойку в размере {rate_str} ({rate_words}) от неуплаченной суммы за каждый календарный день просрочки.

## 5. Форс-мажор

5.1. Стороны освобождаются от ответственности при наступлении обстоятельств непреодолимой силы, подтверждённых компетентным органом.

5.2. Сторона, для которой наступили такие обстоятельства, уведомляет другую сторону в течение 5 (пяти) рабочих дней.

## 6. Особые условия поставки Партии № 2

6.1. Партия № 2 поставляется в рамках пилотного проекта Покупателя по обновлению вычислительной инфраструктуры.

6.2. Поставщик вправе привлечь субподрядчика для монтажа Оборудования Партии № 2, оставаясь ответственным перед Покупателем.

6.3. Приёмка Оборудования Партии № 2 проводится на площадке Покупателя с участием представителей обеих сторон.

## 7. Прочие условия

7.1. Договор вступает в силу с даты подписания и действует до полного исполнения сторонами своих обязательств.

7.2. Споры разрешаются в Арбитражном суде г. Москвы.

---

# Приложение № 1 к Договору № {doc_no}-Т/2026

Перечень Оборудования: серверные стойки, вычислительные узлы, системы хранения данных согласно спецификации сторон.
"""


def make_task(rng, idx):
    supplier, buyer = rng.choice(PARTIES)
    rate_pct, rate_str, rate_words = rng.choice(RATES)
    amount_main, amount_other = rng.sample(AMOUNTS, 2)

    # дедлайн просроченной партии: будний день февраля-июля 2026
    deadline = date(2026, rng.randint(2, 7), rng.randint(1, 25))
    while deadline.weekday() >= 5:
        deadline += timedelta(days=1)
    span = rng.randint(10, 45)
    actual = nearest_workday(deadline + timedelta(days=span))

    wd = working_days_between(deadline, actual)
    cal = (actual - deadline).days
    answer = round(amount_main * rate_pct / 100 * wd, 2)

    # вторая (непросроченная) партия: другой срок, раньше
    deadline_other = deadline - timedelta(days=rng.randint(20, 40))
    while deadline_other.weekday() >= 5:
        deadline_other -= timedelta(days=1)

    party_no = rng.choice([1, 2])
    amounts = {1: amount_main, 2: amount_other}
    deadlines = {1: deadline, 2: deadline_other}
    if party_no == 2:
        amounts = {1: amount_other, 2: amount_main}
        deadlines = {1: deadline_other, 2: deadline}

    contract = CONTRACT_TEMPLATE.format(
        doc_no=rng.randint(10, 99),
        doc_date=date_ru(date(2026, 1, rng.randint(12, 20))),
        supplier=supplier,
        buyer=buyer,
        amount1_str=fmt_amount(amounts[1]),
        amount2_str=fmt_amount(amounts[2]),
        deadline1_ru=date_ru(deadlines[1]),
        deadline2_ru=date_ru(deadlines[2]),
        rate_str=rate_str,
        rate_words=rate_words,
    )

    question_honest = (
        f"Партия № {party_no} должна была быть поставлена не позднее {date_ru(deadline)}, "
        f"фактически поставлена {date_ru(actual)}. Рассчитайте сумму неустойки, "
        f"которую вправе требовать Покупатель, и укажите пункт Договора, на который вы опираетесь."
    )
    question_friendly = (
        f"По условиям п. 4.1 Договора неустойка за нарушение срока поставки составляет "
        f"{rate_str} от стоимости непоставленной в срок Партии за каждый рабочий день просрочки. "
        f"Стоимость Партии № {party_no} — {fmt_amount(amount_main)} рублей. "
        f"Просрочка поставки Партии № {party_no} составила {wd} {plural_days(wd)}. "
        f"Рассчитайте сумму неустойки в рублях: умножьте ставку на стоимость Партии "
        f"и на число рабочих дней просрочки. Укажите пункт Договора, на который вы опираетесь."
    )

    return {
        "id": f"task-{idx:02d}",
        "contract_variant": contract,
        "question_friendly": question_friendly,
        "question_honest": question_honest,
        "answer_rub": answer,
        "working_days": wd,
        "calendar_days": cal,
        "rate_pct": rate_pct,
        "amount_rub": amount_main,
        "party_no": party_no,
        "other_party_amount_rub": amount_other,
        "deadline": deadline.isoformat(),
        "actual": actual.isoformat(),
        "trap_class": TRAP_CLASS,
    }


def main():
    rng = random.Random(SEED)
    tasks = [make_task(rng, i + 1) for i in range(N_TASKS)]

    here = Path(__file__).parent

    def strip(task, question_key):
        t = dict(task)
        t["question"] = t.pop(question_key)
        t.pop("question_friendly" if question_key == "question_honest" else "question_honest")
        return t

    friendly = {
        "name": "friendly",
        "description": "Дружелюбный датасет: в вопросе готовое число рабочих дней и прямая отсылка к п. 4.1. Модель делает только умножение.",
        "seed": SEED,
        "tasks": [strip(t, "question_friendly") for t in tasks],
    }
    honest = {
        "name": "honest",
        "description": "Честный датасет: в вопросе только даты, без намёка на рабочие дни. Модель сама считает период.",
        "seed": SEED,
        "tasks": [strip(t, "question_honest") for t in tasks],
    }

    (here / "dataset_friendly.json").write_text(
        json.dumps(friendly, ensure_ascii=False, indent=2), encoding="utf-8")
    (here / "dataset_honest.json").write_text(
        json.dumps(honest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Сгенерировано задач: {len(tasks)} (seed {SEED})")
    for t in tasks:
        print(f"  {t['id']}: партия {t['party_no']}, {fmt_amount(t['amount_rub'])} руб, "
              f"ставка {t['rate_pct']}%, {t['deadline']} .. {t['actual']} "
              f"({t['working_days']} раб. / {t['calendar_days']} календ.), "
              f"эталон {fmt_amount(int(t['answer_rub']))} руб")


if __name__ == "__main__":
    main()
