using System.Globalization;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Infrastructure.Data;

/// <summary>Хранилище каталога прошивок и заметок к сборкам.</summary>
public sealed class FirmwareRepository
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = false };
    private readonly NexusDatabase _database;

    public FirmwareRepository(NexusDatabase database)
    {
        _database = database;
    }

    public IReadOnlyList<FirmwarePackage> GetAll()
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT * FROM firmware ORDER BY imported_at DESC;";
        using var reader = command.ExecuteReader();
        var result = new List<FirmwarePackage>();
        while (reader.Read())
        {
            result.Add(Map(reader));
        }

        return result;
    }

    public FirmwarePackage? GetById(string id)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT * FROM firmware WHERE id = $id LIMIT 1;";
        command.Parameters.AddWithValue("$id", id);
        using var reader = command.ExecuteReader();
        return reader.Read() ? Map(reader) : null;
    }

    public IReadOnlyList<FirmwarePackage> FindBySha256(string sha256)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT * FROM firmware WHERE sha256 = $sha;";
        command.Parameters.AddWithValue("$sha", sha256);
        using var reader = command.ExecuteReader();
        var result = new List<FirmwarePackage>();
        while (reader.Read())
        {
            result.Add(Map(reader));
        }

        return result;
    }

    public void Upsert(FirmwarePackage package)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO firmware (id, display_name, manufacturer, model, region, version, build_number, codename,
                android_version, format, file_path, size_bytes, sha256, integrity, notes, source, is_user_provided,
                imported_at, last_checked_at, metadata_json, components_json)
            VALUES ($id, $name, $manufacturer, $model, $region, $version, $build, $codename, $android, $format, $path,
                $size, $sha, $integrity, $notes, $source, $user, $imported, $checked, $meta, $components)
            ON CONFLICT(id) DO UPDATE SET
                display_name = excluded.display_name,
                manufacturer = excluded.manufacturer,
                model = excluded.model,
                region = excluded.region,
                version = excluded.version,
                build_number = excluded.build_number,
                codename = excluded.codename,
                android_version = excluded.android_version,
                format = excluded.format,
                file_path = excluded.file_path,
                size_bytes = excluded.size_bytes,
                sha256 = excluded.sha256,
                integrity = excluded.integrity,
                notes = excluded.notes,
                source = excluded.source,
                is_user_provided = excluded.is_user_provided,
                last_checked_at = excluded.last_checked_at,
                metadata_json = excluded.metadata_json,
                components_json = excluded.components_json;
            """;

        command.Parameters.AddWithValue("$id", package.Id);
        command.Parameters.AddWithValue("$name", package.DisplayName);
        AddNullable(command, "$manufacturer", package.Manufacturer);
        AddNullable(command, "$model", package.Model);
        AddNullable(command, "$region", package.Region);
        AddNullable(command, "$version", package.Version);
        AddNullable(command, "$build", package.BuildNumber);
        AddNullable(command, "$codename", package.Codename);
        AddNullable(command, "$android", package.AndroidVersion);
        command.Parameters.AddWithValue("$format", (int)package.Format);
        AddNullable(command, "$path", package.FilePath);
        command.Parameters.AddWithValue("$size", package.SizeBytes);
        AddNullable(command, "$sha", package.Sha256);
        command.Parameters.AddWithValue("$integrity", (int)package.Integrity);
        AddNullable(command, "$notes", package.Notes);
        AddNullable(command, "$source", package.Source);
        command.Parameters.AddWithValue("$user", package.IsUserProvided ? 1 : 0);
        command.Parameters.AddWithValue("$imported", package.ImportedAt.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$checked", package.LastCheckedAt.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$meta", JsonSerializer.Serialize(package.Metadata, JsonOptions));
        command.Parameters.AddWithValue("$components", JsonSerializer.Serialize(package.Components, JsonOptions));
        command.ExecuteNonQuery();
    }

    public void Delete(string id)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "DELETE FROM firmware WHERE id = $id;";
        command.Parameters.AddWithValue("$id", id);
        command.ExecuteNonQuery();
    }

    public IReadOnlyList<FirmwareNote> GetNotes(string firmwareId)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT id, created_at, text FROM firmware_note WHERE firmware_id = $id ORDER BY id DESC;";
        command.Parameters.AddWithValue("$id", firmwareId);
        using var reader = command.ExecuteReader();
        var notes = new List<FirmwareNote>();
        while (reader.Read())
        {
            notes.Add(new FirmwareNote(reader.GetInt64(0), firmwareId, ParseDate(reader.GetString(1)), reader.GetString(2)));
        }

        return notes;
    }

    public void AddNote(string firmwareId, string text)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO firmware_note (firmware_id, created_at, text) VALUES ($id, $at, $text);";
        command.Parameters.AddWithValue("$id", firmwareId);
        command.Parameters.AddWithValue("$at", DateTimeOffset.Now.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$text", text);
        command.ExecuteNonQuery();
    }

    public void DeleteNote(long noteId)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "DELETE FROM firmware_note WHERE id = $id;";
        command.Parameters.AddWithValue("$id", noteId);
        command.ExecuteNonQuery();
    }

    public void AddImportHistory(string firmwareId, string sourcePath, string? sha256, string action)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO firmware_import_history (firmware_id, imported_at, source_path, sha256, action)
            VALUES ($id, $at, $path, $sha, $action);
            """;
        command.Parameters.AddWithValue("$id", firmwareId);
        command.Parameters.AddWithValue("$at", DateTimeOffset.Now.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$path", sourcePath);
        AddNullable(command, "$sha", sha256);
        command.Parameters.AddWithValue("$action", action);
        command.ExecuteNonQuery();
    }

    public IReadOnlyList<string> GetImportHistory(string firmwareId)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT imported_at, action, source_path FROM firmware_import_history WHERE firmware_id = $id ORDER BY id DESC;";
        command.Parameters.AddWithValue("$id", firmwareId);
        using var reader = command.ExecuteReader();
        var list = new List<string>();
        while (reader.Read())
        {
            list.Add($"{ParseDate(reader.GetString(0)):yyyy-MM-dd HH:mm} · {reader.GetString(1)} · {reader.GetString(2)}");
        }

        return list;
    }

    private static FirmwarePackage Map(SqliteDataReader reader)
    {
        var metadata = ReadJson<Dictionary<string, string>>(reader, "metadata_json") ?? new Dictionary<string, string>();
        var components = ReadJson<List<FirmwareComponent>>(reader, "components_json") ?? new List<FirmwareComponent>();

        return new FirmwarePackage
        {
            Id = reader.GetString(reader.GetOrdinal("id")),
            DisplayName = reader.GetString(reader.GetOrdinal("display_name")),
            Manufacturer = GetNullableString(reader, "manufacturer"),
            Model = GetNullableString(reader, "model"),
            Region = GetNullableString(reader, "region"),
            Version = GetNullableString(reader, "version"),
            BuildNumber = GetNullableString(reader, "build_number"),
            Codename = GetNullableString(reader, "codename"),
            AndroidVersion = GetNullableString(reader, "android_version"),
            Format = (FirmwareFormat)reader.GetInt32(reader.GetOrdinal("format")),
            FilePath = GetNullableString(reader, "file_path"),
            SizeBytes = reader.GetInt64(reader.GetOrdinal("size_bytes")),
            Sha256 = GetNullableString(reader, "sha256"),
            Integrity = (IntegrityState)reader.GetInt32(reader.GetOrdinal("integrity")),
            Notes = GetNullableString(reader, "notes"),
            Source = GetNullableString(reader, "source"),
            IsUserProvided = reader.GetInt32(reader.GetOrdinal("is_user_provided")) != 0,
            ImportedAt = ParseDate(reader.GetString(reader.GetOrdinal("imported_at"))),
            LastCheckedAt = ParseDate(reader.GetString(reader.GetOrdinal("last_checked_at"))),
            Metadata = metadata,
            Components = components
        };
    }

    private static T? ReadJson<T>(SqliteDataReader reader, string column)
    {
        var ordinal = reader.GetOrdinal(column);
        if (reader.IsDBNull(ordinal))
        {
            return default;
        }

        try
        {
            return JsonSerializer.Deserialize<T>(reader.GetString(ordinal), JsonOptions);
        }
        catch (JsonException)
        {
            return default;
        }
    }

    private static string? GetNullableString(SqliteDataReader reader, string column)
    {
        var ordinal = reader.GetOrdinal(column);
        return reader.IsDBNull(ordinal) ? null : reader.GetString(ordinal);
    }

    private static void AddNullable(SqliteCommand command, string name, string? value) =>
        command.Parameters.AddWithValue(name, (object?)value ?? DBNull.Value);

    private static DateTimeOffset ParseDate(string value) =>
        DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed)
            ? parsed
            : DateTimeOffset.MinValue;
}

public sealed record FirmwareNote(long Id, string FirmwareId, DateTimeOffset CreatedAt, string Text);
