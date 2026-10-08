"""Правила оценки фермы.

Здесь лежит вся «логика денег»: Honeygain платит за РАЗНЫЕ настоящие
residential/mobile подключения. Один публичный IP = одно оплачиваемое
устройство, остальные за тем же NAT не зарабатывают.

Модуль ничего не изменяет и не маскирует — он только сообщает правду
о том, как выглядит ваша установка со стороны сервиса.
"""
from __future__ import annotations

# Ключевые слова, по которым определяется IP дата-центра / VPS / хостинга.
# Такие адреса сервис не принимает: это не домашний и не мобильный интернет.
HOSTING_HINTS = (
    "hosting", "datacenter", "data center", "cloud", "vps", "server",
    "digitalocean", "hetzner", "ovh", "aws", "amazon", "google", "azure",
    "linode", "vultr", "m247", "cloudflare", "franTech", "leaseweb",
)

BYTES_PER_GB = 1024 ** 3

# Ориентировочная ставка Honeygain: ~$0.05–0.10 за ГБ переданного трафика.
# Точной официальной ставки нет — она зависит от спроса в вашем регионе.
RATE_LOW = 0.05
RATE_HIGH = 0.10


def looks_like_hosting(org: str | None, is_hosting: bool | None = False) -> bool:
    if is_hosting:
        return True
    if not org:
        return False
    low = org.lower()
    return any(h in low for h in HOSTING_HINTS)


def analyse(devices: list[dict]) -> dict:
    """Группирует устройства по публичному IP и считает реальную отдачу."""
    groups: dict[str, list[dict]] = {}
    for d in devices:
        groups.setdefault(d["public_ip"], []).append(d)

    ip_blocks = []
    earning = 0
    idle = 0
    hosting = 0

    for ip, devs in sorted(groups.items()):
        devs_sorted = sorted(devs, key=lambda x: x["first_seen"])
        ip_is_hosting = looks_like_hosting(devs_sorted[0].get("org"), devs_sorted[0].get("is_hosting"))

        # За одним публичным IP оплачивается только первое устройство,
        # а IP дата-центра не оплачивается вообще.
        if ip == "unknown" or ip_is_hosting:
            billable, free = [], devs_sorted
        else:
            billable, free = [devs_sorted[0]], devs_sorted[1:]

        for d in devs:
            d["earning"] = d in billable
            d["reason"] = _reason(d, ip, len(devs))
            if looks_like_hosting(d.get("org"), d.get("is_hosting")):
                hosting += 1

        earning += len(billable)
        idle += len(free)

        ip_blocks.append({
            "ip": ip,
            "org": devs_sorted[0].get("org"),
            "country": devs_sorted[0].get("country"),
            "is_hosting": ip_is_hosting,
            "devices": devs_sorted,
            "billable": len(billable),
            "wasted": len(free),
            "total_gb": round(sum(d.get("bytes_shared") or 0 for d in devs_sorted) / BYTES_PER_GB, 2),
        })

    total_gb = round(sum(d.get("bytes_shared") or 0 for d in devices) / BYTES_PER_GB, 2)

    return {
        "devices": devices,
        "ip_blocks": ip_blocks,
        "total_devices": len(devices),
        "total_ips": len([b for b in ip_blocks if b["ip"] != "unknown"]),
        "earning_devices": earning,
        "wasted_devices": idle,
        "hosting_devices": hosting,
        "total_gb": total_gb,
        "earn_low": round(total_gb * RATE_LOW, 2),
        "earn_high": round(total_gb * RATE_HIGH, 2),
        # Порог выплаты — $20. Всё, что ниже, вы не получите на счёт.
        "payout_threshold": 20.0,
        "below_threshold": round(total_gb * RATE_HIGH, 2) < 20.0,
    }


def _reason(d: dict, ip: str, group_size: int) -> str:
    if ip == "unknown":
        return "Нет данных о публичном IP — агент ещё не отправил отчёт"
    if looks_like_hosting(d.get("org"), d.get("is_hosting")):
        return "IP дата-центра/VPS — такие адреса сервис не оплачивает, риск блокировки аккаунта"
    if group_size > 1 and not d.get("earning"):
        return f"Тот же публичный IP, что и у другого устройства ({ip}) — не оплачивается"
    return "Уникальный публичный IP — оплачивается"


def verdict(stats: dict) -> str:
    if stats["total_devices"] == 0:
        return "Устройств пока нет. Установите агент на первый телефон."
    if stats["hosting_devices"]:
        return (f"{stats['hosting_devices']} из {stats['total_devices']} устройств выходит через IP "
                "дата-центра — это прямое нарушение правил сервиса, такие устройства нужно отключить.")
    if stats["wasted_devices"]:
        return (f"{stats['wasted_devices']} из {stats['total_devices']} устройств делят публичный IP "
                "с другими и не приносят ничего. Решение только одно — реально разные подключения "
                "(мобильные данные каждой SIM, либо интернет родственников с их согласия).")
    return "Все устройства на разных IP — установка настроена корректно."
