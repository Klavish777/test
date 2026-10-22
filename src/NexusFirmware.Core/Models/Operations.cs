namespace NexusFirmware.Core.Models;

public enum OperationState
{
    Draft = 0,
    Preview,
    Queued,
    Running,
    Succeeded,
    Failed,
    Cancelled,
    Blocked
}

public enum OperationRisk
{
    Informational = 0,
    ModifiesDevice,
    Destructive
}

/// <summary>Один шаг плана операции. <see cref="Command"/> — только информационно, показывается пользователю.</summary>
public sealed class OperationStep
{
    public required string Title { get; init; }
    public string? Detail { get; init; }
    public string? Command { get; init; }
    public OperationRisk Risk { get; init; } = OperationRisk.Informational;
    public TimeSpan? EstimatedDuration { get; init; }
}

/// <summary>
/// План операции: то, что пользователь видит и подтверждает до любых изменений на устройстве.
/// </summary>
public sealed class OperationPlan
{
    public required string Title { get; init; }
    public required string DeviceSummary { get; init; }
    public required string FirmwareSummary { get; init; }
    public required IReadOnlyList<OperationStep> Steps { get; init; }
    public IReadOnlyList<CompatibilityItem> Checks { get; init; } = Array.Empty<CompatibilityItem>();
    public IReadOnlyList<string> Warnings { get; init; } = Array.Empty<string>();
    public bool IsDryRun { get; init; }
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.Now;

    public OperationRisk HighestRisk => Steps.Count == 0
        ? OperationRisk.Informational
        : Steps.Max(s => s.Risk);

    public bool RequiresExplicitConfirmation => HighestRisk >= OperationRisk.ModifiesDevice;

    public bool HasBlockingIssues => Checks.Any(c => c.Severity == CompatibilitySeverity.Blocking);
}

public sealed class OperationProgress
{
    public double Percent { get; init; }
    public string Message { get; init; } = "";
    public string? CurrentStep { get; init; }
    public OperationState State { get; init; } = OperationState.Running;

    public static OperationProgress Create(double percent, string message, string? step = null) => new()
    {
        Percent = Math.Clamp(percent, 0, 100),
        Message = message,
        CurrentStep = step
    };
}

public sealed class OperationReport
{
    public required string Title { get; init; }
    public required string DeviceSummary { get; init; }
    public required string FirmwareSummary { get; init; }
    public OperationState State { get; init; }
    public DateTimeOffset StartedAt { get; init; }
    public DateTimeOffset FinishedAt { get; init; }
    public IReadOnlyList<ReportEntry> Entries { get; init; } = Array.Empty<ReportEntry>();
    public IReadOnlyList<string> Artifacts { get; init; } = Array.Empty<string>();
    public string? FailedReason { get; init; }
    public bool IsDryRun { get; init; }

    public TimeSpan Duration => FinishedAt - StartedAt;
}

public sealed record ReportEntry(DateTimeOffset Timestamp, string Level, string Message);

public enum LogLevel
{
    Trace = 0,
    Debug,
    Information,
    Warning,
    Error,
    Critical
}

public sealed record LogEntry(DateTimeOffset Timestamp, LogLevel Level, string Source, string Message)
{
    public string TimeText => Timestamp.ToLocalTime().ToString("HH:mm:ss");
    public string LevelText => Level switch
    {
        LogLevel.Trace => "TRC",
        LogLevel.Debug => "DBG",
        LogLevel.Information => "INF",
        LogLevel.Warning => "WRN",
        LogLevel.Error => "ERR",
        LogLevel.Critical => "CRT",
        _ => "???"
    };
}
