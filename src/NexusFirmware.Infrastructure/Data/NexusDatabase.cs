using Microsoft.Data.Sqlite;

namespace NexusFirmware.Infrastructure.Data;

/// <summary>
/// Локальная база SQLite: каталог прошивок, заметки, снимки устройств, отчёты об операциях
/// и журнал действий. Миграции применяются по возрастанию версии схемы.
/// </summary>
public sealed class NexusDatabase
{
    private readonly string _connectionString;

    public NexusDatabase(string databasePath)
    {
        DatabasePath = databasePath;
        _connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Cache = SqliteCacheMode.Shared
        }.ToString();
    }

    public string DatabasePath { get; }

    public SqliteConnection OpenConnection()
    {
        var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var pragma = connection.CreateCommand();
        pragma.CommandText = "PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;";
        pragma.ExecuteNonQuery();
        return connection;
    }

    public void Initialize()
    {
        var directory = Path.GetDirectoryName(DatabasePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        using var connection = OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = Schema;
        command.ExecuteNonQuery();
    }

    private const string Schema = """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );

        INSERT INTO schema_version (version)
        SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);

        CREATE TABLE IF NOT EXISTS firmware (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            manufacturer TEXT NULL,
            model TEXT NULL,
            region TEXT NULL,
            version TEXT NULL,
            build_number TEXT NULL,
            codename TEXT NULL,
            android_version TEXT NULL,
            format INTEGER NOT NULL DEFAULT 0,
            file_path TEXT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NULL,
            integrity INTEGER NOT NULL DEFAULT 0,
            notes TEXT NULL,
            source TEXT NULL,
            is_user_provided INTEGER NOT NULL DEFAULT 1,
            imported_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            metadata_json TEXT NULL,
            components_json TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_firmware_manufacturer ON firmware (manufacturer);
        CREATE INDEX IF NOT EXISTS ix_firmware_model ON firmware (model);
        CREATE INDEX IF NOT EXISTS ix_firmware_sha256 ON firmware (sha256);

        CREATE TABLE IF NOT EXISTS firmware_note (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firmware_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (firmware_id) REFERENCES firmware (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS device_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            serial_masked TEXT NULL,
            mode TEXT NULL,
            manufacturer TEXT NULL,
            model TEXT NULL,
            android_version TEXT NULL,
            build_id TEXT NULL,
            raw_json TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS operation_report (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            device_summary TEXT NOT NULL,
            firmware_summary TEXT NOT NULL,
            state TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            is_dry_run INTEGER NOT NULL,
            report_path TEXT NULL,
            failed_reason TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            level INTEGER NOT NULL,
            message TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trusted_publisher (
            publisher TEXT PRIMARY KEY,
            added_at TEXT NOT NULL,
            note TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS publisher_key (
            publisher TEXT PRIMARY KEY,
            public_key_pem TEXT NOT NULL,
            added_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS firmware_import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firmware_id TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            source_path TEXT NOT NULL,
            sha256 TEXT NULL,
            action TEXT NOT NULL
        );
        """;
}
