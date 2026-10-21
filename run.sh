#!/usr/bin/env bash
# Запуск Smartphone Repair OS из исходников (Linux/macOS).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "Первый запуск: создание окружения и установка зависимостей..."
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip >/dev/null
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python main.py "$@"
