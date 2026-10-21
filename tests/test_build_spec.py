"""Проверки сборки: путь к корню проекта в PyInstaller spec и кодировка вывода."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "build" / "smartphone_repair_os.spec"


def _resolve_project_root(spec_dir: Path) -> Path:
    """Повторяет логику spec-файла: SPECPATH — это КАТАЛОГ со spec-файлом."""
    spec_dir = spec_dir.resolve()
    if spec_dir.is_file():
        spec_dir = spec_dir.parent
    return spec_dir.parent if (spec_dir.parent / "main.py").is_file() else spec_dir


def test_spec_uses_specpath_as_directory():
    text = SPEC.read_text(encoding="utf-8")
    assert "Path(SPECPATH)" in text
    # Регрессия: раньше корень брался как Path(SPECPATH).parent, то есть на уровень выше.
    assert not re.search(r"Path\(SPECPATH\)\.resolve\(\)\.parent(?!\s*$)", text)


def test_project_root_resolution_matches_repository():
    assert _resolve_project_root(ROOT / "build") == ROOT
    assert (ROOT / "main.py").is_file()
    # Если spec лежит прямо в корне проекта, корень должен определиться так же.
    assert _resolve_project_root(ROOT) == ROOT


def test_spec_datas_exist():
    text = SPEC.read_text(encoding="utf-8")
    for relative in (
        "repair_os/data/migrations",
        "repair_os/resources",
        "repair_os/seed/assets",
        "docs",
    ):
        assert (ROOT / relative).exists(), relative
    assert '"main.py"' in text or "main.py" in text


def test_console_configured_for_utf8():
    """--check печатает кириллицу; на Windows в пайпе это cp1252 без фикса."""
    from repair_os.app import configure_console

    configure_console()
    assert sys.stdout is not None
    encoding = getattr(sys.stdout, "encoding", "") or ""
    assert encoding.lower().replace("-", "") in {"utf8", "utf_8", "utf8mb4", ""}
