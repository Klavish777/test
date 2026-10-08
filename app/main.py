"""Панель мониторинга устройств для заработка на шеринге трафика.

Что делает: собирает честные отчёты от ваших устройств (публичный IP,
тип подключения, провайдер, объём трафика) и показывает, сколько из них
РЕАЛЬНО оплачиваются сервисом.

Что принципиально НЕ делает: не маскирует IP, не подменяет сетевые данные,
не скрывает тот факт, что устройства сидят за одним роутером, не работает
как прокси/VPN. Любая такая функция сделает установку нарушающей правила
сервиса и приведёт к блокировке аккаунта.
"""
from __future__ import annotations

import os
import sys
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

try:  # запуск как пакет: `uvicorn app.main:app`
    from .analysis import analyse, verdict
    from . import store
except ImportError:  # запуск как скрипт: `python app/main.py`
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analysis import analyse, verdict
    import store

app = FastAPI(title="Мониторинг устройств", version="1.0")
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


class Report(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    name: str | None = None
    public_ip: str | None = None
    conn_type: str | None = None          # wifi | cellular | ethernet
    org: str | None = None                # провайдер / ASN, если известен
    country: str | None = None
    is_hosting: bool = False              # True, если IP принадлежит дата-центру
    bytes_shared: int = 0


@app.post("/api/report")
def post_report(r: Report):
    store.upsert(r.model_dump())
    return {"ok": True, "ts": time.time()}


@app.get("/api/devices")
def get_devices():
    rows = [dict(x) for x in store.all_devices()]
    stats = analyse(rows)
    stats["verdict"] = verdict(stats)
    stats["server_time"] = time.time()
    return JSONResponse(stats)


@app.delete("/api/device/{device_id}")
def remove_device(device_id: str):
    store.delete(device_id)
    return {"ok": True}


@app.post("/api/reset")
def reset():
    store.reset()
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "dashboard.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
