#!/usr/bin/env python3
"""Демо-данные: типичная установка из 5 телефонов и того, что с ней не так.

Сценарий:
  - 3 телефона на домашнем Wi-Fi  → один публичный IP, оплачивается только первый
  - 1 телефон на мобильных данных → свой IP, оплачивается
  - 1 «телефон» на VPS            → IP дата-центра, нарушение правил
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import store  # noqa: E402

GB = 1024 ** 3

DEVICES = [
    dict(device_id="phone-01", name="Телефон 1 (Wi-Fi)",  public_ip="85.204.11.42",
         conn_type="wifi",     org="Moldtelecom", country="Moldova", bytes_shared=int(4.2 * GB)),
    dict(device_id="phone-02", name="Телефон 2 (Wi-Fi)",  public_ip="85.204.11.42",
         conn_type="wifi",     org="Moldtelecom", country="Moldova", bytes_shared=int(3.8 * GB)),
    dict(device_id="phone-03", name="Телефон 3 (Wi-Fi)",  public_ip="85.204.11.42",
         conn_type="wifi",     org="Moldtelecom", country="Moldova", bytes_shared=int(3.5 * GB)),
    dict(device_id="phone-04", name="Телефон 4 (Orange)", public_ip="178.132.77.9",
         conn_type="cellular", org="Orange Moldova", country="Moldova", bytes_shared=int(2.1 * GB)),
    dict(device_id="vps-01",   name="VPS (не делайте так)", public_ip="116.202.19.4",
         conn_type="ethernet", org="Hetzner Online GmbH", country="Germany",
         is_hosting=True, bytes_shared=int(6.0 * GB)),
]


def main() -> int:
    store.reset()
    for d in DEVICES:
        store.upsert(d)
    print(f"Загружено демо-устройств: {len(DEVICES)}")
    print("Запустите панель: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
