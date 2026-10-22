using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;

namespace NexusFirmware.Infrastructure.Processes;

public sealed class ExternalToolDefinition
{
    public required string Id { get; init; }
    public required string DisplayName { get; init; }
    public required string ExecutablePath { get; init; }
    public string? Homepage { get; init; }
    public string? Notes { get; init; }
    public bool RequiresElevation { get; init; }
    public bool IsVerifiedPublisher { get; init; }
}

/// <summary>
/// Адаптер для внешних сервисных инструментов, которые пользователь установил сам.
/// Приложение не скачивает и не подменяет такие инструменты; запуск — только по явному действию.
/// </summary>
public sealed class ExternalToolAdapter
{
    private readonly IProcessRunner _runner;
    private readonly ILogBus _log;

    public ExternalToolAdapter(IProcessRunner runner, ILogBus log)
    {
        _runner = runner;
        _log = log;
    }

    public IReadOnlyList<ExternalToolDefinition> KnownTools { get; } = new[]
    {
        new ExternalToolDefinition
        {
            Id = "spflashtool",
            DisplayName = "SP Flash Tool (MediaTek)",
            ExecutablePath = "spflashtool.exe",
            Homepage = "https://spflashtool.com/",
            Notes = "Запускается только вручную; авторизация SLA/DAA остаётся ответственностью инструмента.",
            RequiresElevation = true
        },
        new ExternalToolDefinition
        {
            Id = "odin",
            DisplayName = "Samsung Odin (официальный сервисный инструмент)",
            ExecutablePath = "Odin3.exe",
            Homepage = "https://developer.samsung.com/",
            Notes = "Прошивка Samsung выполняется внешним инструментом.",
            RequiresElevation = true
        },
        new ExternalToolDefinition
        {
            Id = "qfil",
            DisplayName = "Qualcomm QFIL / QPST",
            ExecutablePath = "QFIL.exe",
            Homepage = "https://www.qualcomm.com/",
            Notes = "Требует авторизованный доступ и собственный programmer-файл.",
            RequiresElevation = true
        }
    };

    public async Task<ProcessResult> RunAsync(
        ExternalToolDefinition tool,
        IReadOnlyList<string> arguments,
        TimeSpan? timeout = null,
        CancellationToken cancellationToken = default)
    {
        if (!File.Exists(tool.ExecutablePath))
        {
            _log.Warn("ExternalTool", $"Инструмент «{tool.DisplayName}» не найден по пути «{tool.ExecutablePath}».");
            return ProcessResult.NotStarted(tool.ExecutablePath, "Исполняемый файл внешнего инструмента не найден.");
        }

        if (tool.RequiresElevation)
        {
            _log.Warn("ExternalTool", "Внешний инструмент обычно требует прав администратора: приложение не повышает привилегии автоматически.");
        }

        _log.Info("ExternalTool", $"Запуск внешнего инструмента: {tool.DisplayName}");
        return await _runner.RunAsync(new ProcessRequest
        {
            FileName = tool.ExecutablePath,
            Arguments = arguments,
            Timeout = timeout ?? TimeSpan.FromMinutes(10),
            Description = tool.DisplayName
        }, cancellationToken).ConfigureAwait(false);
    }
}
