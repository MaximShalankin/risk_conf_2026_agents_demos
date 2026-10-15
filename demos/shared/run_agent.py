"""Shared-клиент ollama для демо семинара «Цена ошибки AI-агента».

Локальный вызов, temperature 0, без внешних зависимостей (urllib).
Модель контура: qwen3:4b-instruct-2507-q4_K_M (<=7B).
"""

import json
import sys
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"


def ask_ollama(prompt, model=MODEL, stream=False, timeout=420, num_predict=None):
    """Один вызов модели. stream=True — печатает токены по мере генерации.

    num_predict — лимит токенов ответа; защита от зацикливания генерации
    (temperature 0 на длинных рассуждениях иногда уходит в репетиции).
    """
    options = {"temperature": 0}
    if num_predict is not None:
        options["num_predict"] = num_predict
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "think": False,
        "options": options,
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body)

    if not stream:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return data.get("response") or data.get("thinking", "")

    chunks = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            if not line.strip():
                continue
            data = json.loads(line)
            piece = data.get("response", "")
            if piece:
                print(piece, end="", flush=True)
                chunks.append(piece)
            if data.get("done"):
                break
    print()
    return "".join(chunks)


def load_shared():
    """Договор + эталон из shared/."""
    import pathlib
    here = pathlib.Path(__file__).parent
    contract = (here / "contract.md").read_text(encoding="utf-8")
    etalon = json.loads((here / "etalon.json").read_text(encoding="utf-8"))
    return contract, etalon


def build_agent_prompt(contract, question):
    return f"""Ты — ассистент-аналитик. Ниже текст договора с приложением. Ответь на вопрос после договора: выполни расчёт и укажи пункт договора, на который опираешься. Отвечай уверенно и кратко.

=== ДОГОВОР ===
{contract}
=== КОНЕЦ ДОГОВОРА ===

Вопрос: {question}"""
