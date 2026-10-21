-- Миграция 002: физические размеры платы и контрольная сумма пакета.
-- Нужны для корректного масштаба 3D-сцены и проверки целостности импортированных данных.

ALTER TABLE board_models ADD COLUMN width_mm REAL;
ALTER TABLE board_models ADD COLUMN length_mm REAL;
ALTER TABLE board_models ADD COLUMN thickness_mm REAL;
ALTER TABLE board_models ADD COLUMN package_checksum TEXT;
ALTER TABLE board_models ADD COLUMN imported_at TEXT;

CREATE INDEX IF NOT EXISTS ix_board_models_checksum ON board_models (package_checksum);
