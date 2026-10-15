#!/bin/zsh
# Демо 1 «Уверенный ответ» — запуск одной командой
cd "$(dirname "$0")"
# Прогрев: загрузить модель в память, чтобы первый ответ не ждал
curl -s http://localhost:11434/api/generate -d '{"model":"qwen3:4b-instruct-2507-q4_K_M","keep_alive":"10m"}' > /dev/null
python3 demo1.py
