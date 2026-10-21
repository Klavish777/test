"""Общие фикстуры тестов."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Qt в тестах работает без экрана.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from repair_os.core.paths import build_paths  # noqa: E402
from repair_os.data.database import open_database  # noqa: E402
from repair_os.seed.demo_data import DemoSeeder  # noqa: E402
from repair_os.services.context import AppContext  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    database = open_database(tmp_path / "test.sqlite3")
    yield database
    database.close()


@pytest.fixture()
def seeded_db(tmp_path):
    database = open_database(tmp_path / "seeded.sqlite3")
    paths = build_paths(tmp_path / "data").ensure()
    DemoSeeder(database, paths).seed()
    yield database
    database.close()


@pytest.fixture()
def context(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIR_OS_DATA", str(tmp_path / "appdata"))
    ctx = AppContext.create(tmp_path / "appdata")
    yield ctx
    ctx.close()


@pytest.fixture()
def empty_context(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIR_OS_DATA", str(tmp_path / "empty"))
    ctx = AppContext.create(tmp_path / "empty", seed_demo=False)
    yield ctx
    ctx.close()
