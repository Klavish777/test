using System.Globalization;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Infrastructure.Data;

/// <summary>Журнал действий, снимки устройств и записи об отчётах.</summary>
public sealed class DiagnosticsRepository
{
    private readonly NexusDatabase _database;

    public DiagnosticsRepository(NexusDatabase database)
    {
        _database = database;
    }

    public void SaveDeviceSnapshot(DeviceInfo device)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO device_snapshot (captured_at, serial_masked, mode, manufacturer, model, android_version, build_id)
            VALUES ($at, $serial, $mode, $manufacturer, $model, $android, $build);
            """;
        command.Parameters.AddWithValue("$at", DateTimeOffset.Now.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$serial", device.MaskedSerial);
        command.Parameters.AddWithValue("$mode", device.Mode.ToString());
        command.Parameters.AddWithValue("$manufacturer", (object?)device.Manufacturer ?? DBNull.Value);
        command.Parameters.AddWithValue("$model", (object?)device.Model ?? DBNull.Value);
        command.Parameters.AddWithValue("$android", (object?)device.AndroidVersion ?? DBNull.Value);
        command.Parameters.AddWithValue("$build", (object?)device.BuildId ?? DBNull.Value);
        command.ExecuteNonQuery();
    }

    public void SaveReport(OperationReport report, string? reportPath)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            INSERT INTO operation_report (id, title, device_summary, firmware_summary, state, started_at, finished_at, is_dry_run, report_path, failed_reason)
            VALUES ($id, $title, $device, $firmware, $state, $started, $finished, $dry, $path, $reason);
            """;
        command.Parameters.AddWithValue("$id", Guid.NewGuid().ToString("N"));
        command.Parameters.AddWithValue("$title", report.Title);
        command.Parameters.AddWithValue("$device", report.DeviceSummary);
        command.Parameters.AddWithValue("$firmware", report.FirmwareSummary);
        command.Parameters.AddWithValue("$state", report.State.ToString());
        command.Parameters.AddWithValue("$started", report.StartedAt.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$finished", report.FinishedAt.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$dry", report.IsDryRun ? 1 : 0);
        command.Parameters.AddWithValue("$path", (object?)reportPath ?? DBNull.Value);
        command.Parameters.AddWithValue("$reason", (object?)report.FailedReason ?? DBNull.Value);
        command.ExecuteNonQuery();
    }

    public void WriteJournal(LogEntry entry)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO journal (created_at, source, level, message) VALUES ($at, $source, $level, $message);";
        command.Parameters.AddWithValue("$at", entry.Timestamp.ToString("O", CultureInfo.InvariantCulture));
        command.Parameters.AddWithValue("$source", entry.Source);
        command.Parameters.AddWithValue("$level", (int)entry.Level);
        command.Parameters.AddWithValue("$message", entry.Message);
        command.ExecuteNonQuery();
    }

    public IReadOnlyList<ReportSummary> GetReports(int limit = 100)
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = """
            SELECT title, device_summary, state, started_at, finished_at, is_dry_run, report_path
            FROM operation_report ORDER BY finished_at DESC LIMIT $limit;
            """;
        command.Parameters.AddWithValue("$limit", limit);
        using var reader = command.ExecuteReader();
        var list = new List<ReportSummary>();
        while (reader.Read())
        {
            list.Add(new ReportSummary(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                ParseDate(reader.GetString(3)),
                ParseDate(reader.GetString(4)),
                reader.GetInt32(5) != 0,
                reader.IsDBNull(6) ? null : reader.GetString(6)));
        }

        return list;
    }

    public void ClearJournal()
    {
        using var connection = _database.OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText = "DELETE FROM journal;";
        command.ExecuteNonQuery();
    }

    private static DateTimeOffset ParseDate(string value) =>
        DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed)
            ? parsed
            : DateTimeOffset.MinValue;
}

public sealed record ReportSummary(
    string Title,
    string DeviceSummary,
    string State,
    DateTimeOffset StartedAt,
    DateTimeOffset FinishedAt,
    bool IsDryRun,
    string? ReportPath)
{
    public string ModeText => IsDryRun ? "Dry Run" : "Реальное";

    public string FinishedText => FinishedAt.ToLocalTime().ToString("yyyy-MM-dd HH:mm");
}
