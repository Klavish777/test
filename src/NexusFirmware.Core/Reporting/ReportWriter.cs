using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Core.Reporting;

/// <summary>Формирование отчётов об операциях в Markdown и JSON.</summary>
public static class ReportWriter
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() }
    };

    public static string ToMarkdown(OperationReport report)
    {
        var sb = new StringBuilder();
        sb.AppendLine($"# {report.Title}");
        sb.AppendLine();
        sb.AppendLine($"- **Устройство:** {report.DeviceSummary}");
        sb.AppendLine($"- **Прошивка:** {report.FirmwareSummary}");
        sb.AppendLine($"- **Режим:** {(report.IsDryRun ? "Dry Run (без изменений на устройстве)" : "Реальное выполнение")}");
        sb.AppendLine($"- **Итог:** {StateText(report.State)}");
        sb.AppendLine($"- **Начало:** {report.StartedAt:yyyy-MM-dd HH:mm:ss}");
        sb.AppendLine($"- **Окончание:** {report.FinishedAt:yyyy-MM-dd HH:mm:ss}");
        sb.AppendLine($"- **Длительность:** {report.Duration.TotalSeconds:0.0} с");
        if (!string.IsNullOrWhiteSpace(report.FailedReason))
        {
            sb.AppendLine($"- **Причина ошибки:** {report.FailedReason}");
        }

        sb.AppendLine();
        sb.AppendLine("## Журнал");
        sb.AppendLine();
        sb.AppendLine("| Время | Уровень | Сообщение |");
        sb.AppendLine("|---|---|---|");
        foreach (var entry in report.Entries)
        {
            sb.AppendLine($"| {entry.Timestamp:HH:mm:ss.fff} | {entry.Level} | {Escape(entry.Message)} |");
        }

        if (report.Artifacts.Count > 0)
        {
            sb.AppendLine();
            sb.AppendLine("## Артефакты");
            foreach (var artifact in report.Artifacts)
            {
                sb.AppendLine($"- `{artifact}`");
            }
        }

        sb.AppendLine();
        sb.AppendLine($"_Отчёт создан NEXUS Firmware Studio {DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss zzz}_");
        return sb.ToString();
    }

    public static string ToJson(OperationReport report) => JsonSerializer.Serialize(new
    {
        report.Title,
        report.DeviceSummary,
        report.FirmwareSummary,
        State = report.State.ToString(),
        report.StartedAt,
        report.FinishedAt,
        DurationSeconds = Math.Round(report.Duration.TotalSeconds, 3),
        report.FailedReason,
        report.IsDryRun,
        report.Artifacts,
        Entries = report.Entries.Select(e => new { e.Timestamp, e.Level, e.Message })
    }, JsonOptions);

    public static string StateText(OperationState state) => state switch
    {
        OperationState.Succeeded => "Успешно",
        OperationState.Failed => "Ошибка",
        OperationState.Cancelled => "Отменено",
        OperationState.Blocked => "Заблокировано",
        OperationState.Running => "Выполняется",
        OperationState.Queued => "В очереди",
        OperationState.Preview => "Предварительный просмотр",
        _ => "Черновик"
    };

    private static string Escape(string text) => text.Replace("|", "\\|").Replace("\r", " ").Replace("\n", " ");
}
