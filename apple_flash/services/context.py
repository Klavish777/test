"""Единый контекст сервисов Apple Flash Studio."""

from __future__ import annotations

from pathlib import Path

from apple_flash.core.logging_setup import setup_logging
from apple_flash.core.paths import StudioPaths
from apple_flash.core.security import compute_hashes
from apple_flash.data.store import StudioStore
from apple_flash.services.device_detector import DeviceDetector
from apple_flash.services.driver_diagnostics import DriverDiagnostics
from apple_flash.services.flash_engine import FlashEngine
from apple_flash.services.ipsw_inspector import IpswInspector, create_demo_ipsw_bundle


class StudioContext:
    """Контейнер состояния, хранилища и всех сервисов приложения."""

    def __init__(self, paths: StudioPaths, store: StudioStore) -> None:
        self.paths = paths
        self.store = store
        custom_tools = store.get_setting("custom_tools_dir", "").strip()
        eff_tools_dir = Path(custom_tools) if custom_tools else paths.tools_dir

        self.inspector = IpswInspector()
        self.detector = DeviceDetector(tools_dir=eff_tools_dir)
        self.diagnostics = DriverDiagnostics(tools_dir=eff_tools_dir)
        self.flash_engine = FlashEngine(
            store=store,
            inspector=self.inspector,
            default_tools_dir=eff_tools_dir,
        )

    @classmethod
    def create(
        cls,
        data_dir: Path | str | None = None,
        *,
        seed_demo: bool = True,
        verbose: bool = False,
    ) -> StudioContext:
        paths = StudioPaths.create(data_dir)
        setup_logging(paths.logs_dir, verbose=verbose)
        store = StudioStore(paths.db_file)
        ctx = cls(paths, store)

        if seed_demo and store.get_setting("demo_seeded", "") != "1":
            ctx.install_demo_mockups()
            store.set_setting("demo_seeded", "1")
        return ctx

    def update_tools_dir(self, path_str: str) -> None:
        cleaned = path_str.strip()
        self.store.set_setting("custom_tools_dir", cleaned)
        eff = Path(cleaned) if cleaned else self.paths.tools_dir
        self.detector.tools_dir = eff
        self.diagnostics.tools_dir = eff
        self.flash_engine.default_tools_dir = eff

    def install_demo_mockups(self) -> int:
        """Создаёт и регистрирует 3 учебных макета .ipsw (iPhone, iPad, MacBook) с расчётом SHA-256."""
        demo_dir = self.paths.ipsw_dir / "demo_mockups"
        files = create_demo_ipsw_bundle(demo_dir)
        for path in files:
            manifest = self.inspector.inspect(path)
            sha256, sha1 = compute_hashes(path)
            self.store.upsert_ipsw_from_manifest(
                manifest,
                sha256=sha256,
                sha1=sha1,
                expected_hash=sha256,
                notes="Демонстрационный макет IPSW для проверки интерфейса и режима Dry-Run.",
            )
        return len(files)

    def remove_demo_mockups(self) -> int:
        paths = self.store.delete_demo_ipsw()
        removed = 0
        for p in paths:
            try:
                if p.is_file() and p.name.startswith("DEMO_"):
                    p.unlink()
                    removed += 1
            except OSError:
                pass
        return max(removed, len(paths))

    def close(self) -> None:
        self.store.close()
