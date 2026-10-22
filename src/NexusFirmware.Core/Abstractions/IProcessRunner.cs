namespace NexusFirmware.Core.Abstractions;

/// <summary>Описание запуска внешнего инструмента. Аргументы передаются списком — без склейки в строку.</summary>
public sealed class ProcessRequest
{
    public required string FileName { get; init; }
    public IReadOnlyList<string> Arguments { get; init; } = Array.Empty<string>();
    public string? WorkingDirectory { get; init; }
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(30);
    public bool RedactOutput { get; init; } = true;
    public IReadOnlyDictionary<string, string>? Environment { get; init; }
    public string? Description { get; init; }

    public string SafeDescription => Description ?? $"{Path.GetFileName(FileName)} {string.Join(' ', Arguments)}";
}

public sealed class ProcessResult
{
    public required string FileName { get; init; }
    public IReadOnlyList<string> Arguments { get; init; } = Array.Empty<string>();
    public int ExitCode { get; init; }
    public string StandardOutput { get; init; } = string.Empty;
    public string StandardError { get; init; } = string.Empty;
    public bool TimedOut { get; init; }
    public bool Cancelled { get; init; }
    public bool Started { get; init; } = true;
    public string? StartError { get; init; }
    public TimeSpan Duration { get; init; }
    public DateTimeOffset StartedAt { get; init; } = DateTimeOffset.Now;

    public bool Succeeded => Started && !TimedOut && !Cancelled && ExitCode == 0;

    public string CombinedOutput => string.Join(Environment.NewLine,
        new[] { StandardOutput, StandardError }.Where(s => !string.IsNullOrWhiteSpace(s)));

    public static ProcessResult NotStarted(string fileName, string error) => new()
    {
        FileName = fileName,
        Started = false,
        StartError = error,
        ExitCode = -1
    };
}

/// <summary>Запуск внешнего процесса с тайм-аутом, отменой и перехватом stdout/stderr.</summary>
public interface IProcessRunner
{
    Task<ProcessResult> RunAsync(ProcessRequest request, CancellationToken cancellationToken = default);

    Task<bool> IsAvailableAsync(string fileName, CancellationToken cancellationToken = default);
}
