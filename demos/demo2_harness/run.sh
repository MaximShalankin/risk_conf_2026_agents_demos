#!/bin/bash
# Демо 2 «Харнесс в прямом эфире»: прогрев модели + прогон харнесса.
# По умолчанию — подвыборка 6+6 задач (короткий прогон, 2-3 минуты). Полный прогон: ./run.sh --full
set -euo pipefail
cd "$(dirname "$0")"

MODEL="qwen3:4b-instruct-2507-q4_K_M"

# Проверка, что ollama поднят
if ! curl -sf http://localhost:11434/api/tags > /dev/null; then
    echo "Ollama недоступен на localhost:11434. Запустите: ollama serve"
    exit 1
fi

# Прогрев: загружаем модель в память, чтобы первый ответ не ждал загрузки
echo "Прогрев модели ${MODEL}..."
curl -s http://localhost:11434/api/generate -d "{
  \"model\": \"${MODEL}\",
  \"prompt\": \"Ответь одним словом: готов\",
  \"stream\": false,
  \"think\": false,
  \"keep_alive\": \"15m\",
  \"options\": {\"temperature\": 0}
}" > /dev/null
echo "Модель загружена. Запускаем харнесс."

python3 demo2.py "$@"
