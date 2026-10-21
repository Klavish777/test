-- SQL-схема базы данных Smartphone Repair OS (миграция 001).

-- Демонстрационные записи помечаются флагом is_demo = 1 и в интерфейсе
-- подписаны как «демо». Реальные пользовательские данные имеют is_demo = 0.

CREATE TABLE IF NOT EXISTS brands (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    country         TEXT,
    website         TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS devices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id            INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name                TEXT    NOT NULL,
    model_code          TEXT    NOT NULL,
    codename            TEXT,
    hardware_revision   TEXT,
    soc                 TEXT,
    soc_platform        TEXT,
    ram                 TEXT,
    storage             TEXT,
    os_versions         TEXT,
    release_year        INTEGER,
    notes               TEXT,
    source              TEXT,
    verified            INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
    is_demo             INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_devices_identity
    ON devices (brand_id, lower(model_code), lower(COALESCE(codename, '')), lower(COALESCE(hardware_revision, '')));
CREATE INDEX IF NOT EXISTS ix_devices_brand ON devices (brand_id);
CREATE INDEX IF NOT EXISTS ix_devices_name ON devices (name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_devices_model_code ON devices (model_code COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_devices_codename ON devices (codename COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS device_variants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    model_code      TEXT    NOT NULL,
    region          TEXT,
    csc             TEXT,
    ram             TEXT,
    storage         TEXT,
    bootloader      TEXT,
    notes           TEXT,
    is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_variants_device ON device_variants (device_id);
CREATE INDEX IF NOT EXISTS ix_variants_model_code ON device_variants (model_code COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS firmware_sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    url             TEXT,
    kind            TEXT    NOT NULL DEFAULT 'community'
                    CHECK (kind IN ('official', 'community', 'local', 'vendor_tool')),
    trusted         INTEGER NOT NULL DEFAULT 0 CHECK (trusted IN (0, 1)),
    notes           TEXT,
    last_checked    TEXT,
    is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS firmware (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id               INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    variant_id              INTEGER REFERENCES device_variants(id) ON DELETE SET NULL,
    source_id               INTEGER REFERENCES firmware_sources(id) ON DELETE SET NULL,
    title                   TEXT,
    file_name               TEXT    NOT NULL,
    model_code              TEXT,
    os_version              TEXT,
    build_number            TEXT,
    region                  TEXT,
    csc                     TEXT,
    release_date            TEXT,
    file_size               INTEGER,
    checksum_sha256         TEXT,
    checksum_reference      TEXT,
    download_url            TEXT,
    local_path              TEXT,
    install_instructions    TEXT,
    compatibility_notes     TEXT,
    min_bootloader          TEXT,
    verification_status     TEXT NOT NULL DEFAULT 'unverified'
                            CHECK (verification_status IN ('unverified', 'community', 'verified', 'rejected')),
    is_demo                 INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_firmware_device ON firmware (device_id);
CREATE INDEX IF NOT EXISTS ix_firmware_model_code ON firmware (model_code COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_firmware_build ON firmware (build_number COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_firmware_file_name ON firmware (file_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_firmware_region ON firmware (region);

CREATE TABLE IF NOT EXISTS board_models (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    name            TEXT    NOT NULL,
    board_code      TEXT,
    revision        TEXT,
    package_path    TEXT,
    format          TEXT,
    has_3d          INTEGER NOT NULL DEFAULT 0 CHECK (has_3d IN (0, 1)),
    photo_top       TEXT,
    photo_bottom    TEXT,
    source          TEXT,
    license_note    TEXT,
    notes           TEXT,
    is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_board_models_device ON board_models (device_id);
CREATE INDEX IF NOT EXISTS ix_board_models_code ON board_models (board_code COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS board_components (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    board_model_id      INTEGER NOT NULL REFERENCES board_models(id) ON DELETE CASCADE,
    designator          TEXT    NOT NULL,
    side                TEXT    NOT NULL DEFAULT 'top' CHECK (side IN ('top', 'bottom')),
    layer               TEXT,
    component_type      TEXT,
    part_marking        TEXT,
    purpose             TEXT,
    package_type        TEXT,
    pos_x               REAL,
    pos_y               REAL,
    pos_z               REAL,
    size_x              REAL,
    size_y              REAL,
    size_z              REAL,
    rotation            REAL DEFAULT 0,
    marker_u            REAL,
    marker_v            REAL,
    notes               TEXT,
    metadata_json       TEXT,
    is_demo             INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_components_designator
    ON board_components (board_model_id, designator);
CREATE INDEX IF NOT EXISTS ix_components_board ON board_components (board_model_id);
CREATE INDEX IF NOT EXISTS ix_components_layer ON board_components (board_model_id, layer);

CREATE TABLE IF NOT EXISTS board_annotations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    board_model_id      INTEGER NOT NULL REFERENCES board_models(id) ON DELETE CASCADE,
    component_id        INTEGER REFERENCES board_components(id) ON DELETE CASCADE,
    label               TEXT    NOT NULL,
    body                TEXT,
    color               TEXT DEFAULT '#3d8bfd',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_annotations_board ON board_annotations (board_model_id);

CREATE TABLE IF NOT EXISTS technical_documents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT    NOT NULL,
    category            TEXT    NOT NULL DEFAULT 'general',
    doc_type            TEXT    NOT NULL DEFAULT 'pdf'
                        CHECK (doc_type IN ('pdf', 'schematic', 'boardview', 'photo', 'instruction', 'note', 'link', 'other')),
    device_id           INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    brand_id            INTEGER REFERENCES brands(id) ON DELETE SET NULL,
    file_path           TEXT,
    source_url          TEXT,
    description         TEXT,
    tags                TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
                        CHECK (verification_status IN ('unverified', 'community', 'verified', 'rejected')),
    verified_at         TEXT,
    license_note        TEXT,
    is_demo             INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_documents_device ON technical_documents (device_id);
CREATE INDEX IF NOT EXISTS ix_documents_category ON technical_documents (category);
CREATE INDEX IF NOT EXISTS ix_documents_title ON technical_documents (title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS component_references (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    document_id         INTEGER REFERENCES technical_documents(id) ON DELETE SET NULL,
    designator          TEXT,
    component_type      TEXT,
    marking             TEXT,
    description         TEXT,
    source_url          TEXT,
    is_demo             INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_component_refs_device ON component_references (device_id);
CREATE INDEX IF NOT EXISTS ix_component_refs_designator ON component_references (designator COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_component_refs_marking ON component_references (marking COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS repair_notes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    board_component_id  INTEGER REFERENCES board_components(id) ON DELETE SET NULL,
    title               TEXT    NOT NULL,
    body                TEXT,
    category            TEXT    NOT NULL DEFAULT 'general',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_notes_device ON repair_notes (device_id);

CREATE TABLE IF NOT EXISTS favorites (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL UNIQUE REFERENCES devices(id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recent_devices (
    device_id       INTEGER PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    opened_at       TEXT NOT NULL DEFAULT (datetime('now')),
    open_count      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS ix_recent_opened ON recent_devices (opened_at DESC);

CREATE TABLE IF NOT EXISTS app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity          TEXT NOT NULL,
    entity_id       INTEGER,
    action          TEXT NOT NULL,
    summary         TEXT,
    changes_json    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log (entity, entity_id, created_at DESC);
