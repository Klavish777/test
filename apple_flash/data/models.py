"""Модели данных Apple Flash Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from apple_flash.data.apple_catalog import CHIP_BY_CPID, FAMILY_LABELS, resolve_product_name

MODE_LABELS: dict[str, str] = {
    "normal": "Обычный режим (Normal / USBMux)",
    "recovery": "Режим восстановления (Recovery · iBoot)",
    "dfu": "Режим DFU (BootROM · 05ac:1227)",
    "wtf": "Режим WTF (05ac:1222)",
}

FLASH_ACTION_LABELS: dict[str, str] = {
    "update": "Обновление с сохранением данных (Update)",
    "erase": "Чистая перепрошивка со стиранием (Clean Restore)",
    "revive_mac": "Оживление MacBook без удаления данных (Revive DFU)",
    "exit_recovery": "Выход из режима Recovery",
    "enter_recovery": "Перевод устройства в режим Recovery",
}


@dataclass
class ConnectedDevice:
    uid: str  # UDID или ECID
    mode: str  # normal | recovery | dfu | wtf
    product_type: str | None = None
    marketing_name: str = "Устройство Apple"
    family: str = "unknown"  # iphone | ipad | macbook | unknown
    ecid: str | None = None
    udid: str | None = None
    cpid: int | None = None
    bdid: int | None = None
    board_config: str | None = None
    os_version: str | None = None
    build_version: str | None = None
    serial_number: str | None = None
    device_name: str | None = None
    battery_percent: int | None = None
    usb_driver: str | None = None
    source_backend: str = "usb"
    is_virtual: bool = False

    @property
    def mode_label(self) -> str:
        return MODE_LABELS.get(self.mode, self.mode)

    @property
    def family_label(self) -> str:
        return FAMILY_LABELS.get(self.family, self.family)

    @property
    def chip_label(self) -> str:
        if self.cpid is not None:
            name = CHIP_BY_CPID.get(self.cpid)
            return f"{name} (0x{self.cpid:04X})" if name else f"0x{self.cpid:04X}"
        return "—"

    @property
    def display_title(self) -> str:
        base = self.marketing_name or resolve_product_name(self.product_type, self.cpid)
        if self.is_virtual:
            return f"[МАКЕТ] {base}"
        return base


@dataclass
class IpswManifestInfo:
    path: Path
    file_name: str
    file_size: int
    product_version: str
    build_version: str
    family: str  # iphone | ipad | macbook | universal | unknown
    supported_product_types: list[str] = field(default_factory=list)
    supported_cpids: list[int] = field(default_factory=list)
    board_configs: list[str] = field(default_factory=list)
    restore_variants: list[str] = field(default_factory=list)
    has_erase_variant: bool = True
    has_upgrade_variant: bool = True
    has_baseband: bool = False
    has_sep: bool = False
    zip_entries_count: int = 0
    missing_components: list[str] = field(default_factory=list)
    is_demo_mockup: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class IpswRecord:
    id: int | None
    file_name: str
    local_path: str
    file_size: int
    family: str
    product_version: str
    build_version: str
    supported_products: list[str] = field(default_factory=list)
    supported_cpids: list[int] = field(default_factory=list)
    board_configs: list[str] = field(default_factory=list)
    has_erase: bool = True
    has_upgrade: bool = True
    sha256: str | None = None
    sha1: str | None = None
    expected_hash: str | None = None
    verified_state: str = "unchecked"  # unchecked | verified | mismatch | missing
    is_demo: bool = False
    notes: str | None = None
    added_at: str | None = None

    @property
    def file_exists(self) -> bool:
        return bool(self.local_path) and Path(self.local_path).is_file()

    @property
    def family_label(self) -> str:
        return FAMILY_LABELS.get(self.family, self.family)

    @property
    def models_preview(self) -> str:
        if not self.supported_products:
            return "—"
        names = [resolve_product_name(pt) for pt in self.supported_products[:3]]
        rest = len(self.supported_products) - 3
        text = ", ".join(names)
        return f"{text} (+{rest})" if rest > 0 else text


@dataclass
class CompatibilityVerdict:
    level: str  # compatible | warning | incompatible
    headline: str
    details: list[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        return self.level != "incompatible"


@dataclass
class DriverCheckItem:
    key: str
    title: str
    status: str  # ok | warning | missing | info
    summary: str
    recommendation: str = ""


@dataclass
class FlashJobConfig:
    action: str  # update | erase | revive_mac | exit_recovery | enter_recovery
    device: ConnectedDevice | None = None
    ipsw_path: Path | None = None
    shsh_path: Path | None = None
    backend: str = "auto"  # auto | pymobiledevice3 | idevicerestore
    dry_run: bool = True
    custom_tools_dir: Path | None = None


@dataclass
class FlashSessionRecord:
    id: int | None
    started_at: str
    finished_at: str | None
    device_title: str
    device_uid: str
    product_type: str | None
    family: str
    action: str
    backend: str
    ipsw_name: str | None
    ipsw_build: str | None
    dry_run: bool
    status: str  # success | failed | cancelled
    exit_code: int
    command_line: str
    log_text: str
