using NexusFirmware.Core.Models;

namespace NexusFirmware.Core.Abstractions;

/// <summary>Канал журналирования для интерфейса и файловых журналов.</summary>
public interface ILogBus
{
    event EventHandler<LogEntry>? Appended;

    void Write(LogLevel level, string source, string message);

    IReadOnlyList<LogEntry> Recent { get; }

    void Clear();
}

public static class LogBusExtensions
{
    public static void Info(this ILogBus bus, string source, string message) => bus.Write(LogLevel.Information, source, message);

    public static void Warn(this ILogBus bus, string source, string message) => bus.Write(LogLevel.Warning, source, message);

    public static void Error(this ILogBus bus, string source, string message) => bus.Write(LogLevel.Error, source, message);

    public static void Debug(this ILogBus bus, string source, string message) => bus.Write(LogLevel.Debug, source, message);
}
