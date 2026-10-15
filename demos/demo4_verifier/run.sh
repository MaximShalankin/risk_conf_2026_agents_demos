#!/bin/zsh
# Демо 4 «Тот же отказ, но с верификатором» — запуск одной командой
cd "$(dirname "$0")"
curl -s http://localhost:11434/api/generate -d '{"model":"qwen3:4b-instruct-2507-q4_K_M","keep_alive":"10m"}' > /dev/null
python3 demo4.py
