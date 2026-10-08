#!/usr/bin/env python3
"""Агент устройства: сообщает панели ЧЕСТНЫЕ данные о подключении.

Запускается на каждом телефоне (Termux) или компьютере. Ничего не
подменяет и не маскирует — просто отвечает на вопрос «какой у этого
устройства настоящий публичный IP и кто провайдер».

    python agent/agent.py --server http://192.168.1.10:8000 --name "Телефон 1"

Для офлайн-проверки (без отправки):
    python agent/agent.py --once
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from urllib.error import URLError

INTERVAL = 600  # секунд между отчётами

# Публичные сервисы определения IP. Можно указать свой через --ip-url.
IP_URL = "https://api.ipify.org?format=json"
META_URL = "https://ipapi.co/{ip}/json/"


def http_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": "farm-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def detect_public_ip(ip_url: str) -> str | None:
    try:
        data = http_json(ip_url)
        return data.get("ip")
    except (URLError, ValueError, OSError) as e:
        print(f"[!] не удалось определить публичный IP: {e}", file=sys.stderr)
        return None


def detect_meta(ip: str) -> dict:
    """Провайдер, страна и признак дата-центра. Необязательно — ошибки терпимы."""
    try:
        data = http_json(META_URL.format(ip=ip))
        return {
            "org": data.get("org") or data.get("asn"),
            "country": data.get("country_name") or data.get("country"),
            # ipapi.co не даёт прямой флаг хостинга — берём org на разбор серверу.
        }
    except Exception:
        return {}


def detect_conn_type() -> str:
    """Wi-Fi или мобильные данные — по имени интерфейса маршрута по умолчанию."""
    try:
        out = subprocess.run(["ip", "route", "get", "1.1.1.1"],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"dev\s+(\S+)", out)
        if m:
            iface = m.group(1)
            if iface.startswith(("rmnet", "ccmni", "wwan", "rmnet_data")):
                return "cellular"
            if iface.startswith(("wlan", "eth", "en")):
                return "wifi" if iface.startswith("wlan") else "ethernet"
            return iface
    except Exception:
        pass
    return "unknown"


def report(server: str, payload: dict) -> bool:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{server.rstrip('/')}/api/report", data=body,
        headers={"Content-Type": "application/json", "User-Agent": "farm-agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"[!] отправка не удалась: {e}", file=sys.stderr)
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Агент мониторинга устройства")
    p.add_argument("--server", help="адрес панели, например http://192.168.1.10:8000")
    p.add_argument("--name", help="человекочитаемое имя устройства")
    p.add_argument("--device-id", help="постоянный ID (по умолчанию — имя хоста)")
    p.add_argument("--ip", help="вручную задать публичный IP (для тестов)")
    p.add_argument("--ip-url", default=IP_URL, help="сервис определения IP")
    p.add_argument("--bytes", type=int, default=0, help="сколько байт отдано сервису")
    p.add_argument("--interval", type=int, default=INTERVAL)
    p.add_argument("--once", action="store_true", help="один отчёт и выход")
    args = p.parse_args()

    device_id = args.device_id or __import__("socket").gethostname()
    name = args.name or device_id

    ip = args.ip or detect_public_ip(args.ip_url)
    meta = detect_meta(ip) if ip else {}
    conn = detect_conn_type()

    payload = {
        "device_id": device_id,
        "name": name,
        "public_ip": ip,
        "conn_type": conn,
        "org": meta.get("org"),
        "country": meta.get("country"),
        "bytes_shared": args.bytes,
    }

    print(f"Устройство: {name}")
    print(f"Публичный IP: {ip or 'не определён'}")
    print(f"Подключение: {conn}")
    print(f"Провайдер: {meta.get('org') or 'неизвестен'}")

    if not args.server:
        print("\n(--server не указан — данные показаны, но не отправлены)")
        return 0

    while True:
        if report(args.server, payload):
            print(f"[ok] отчёт отправлен на {args.server}")
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
