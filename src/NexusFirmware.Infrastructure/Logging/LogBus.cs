using System.Collections.ObjectModel;
using NexusFirmware.Core.Abstractions;
using NexusFirmware.Core.Models;
using NexusFirmware.Core.Safety;
using Serilog;

namespace NexusFirmware.Infrastructure.Logging;

/// <summary>Журнал в памяти + запись в файл через Serilog.</summary>
public sealed class LogBus : ILogBus
{
    private const int MaxRecent = 2000;
    private readonly List<LogEntry> _recent = new();
    private readonly ILogger? _fileLogger;
    private readonly object _gate = new();

    public LogBus(ILogger? fileLogger = null)
    {
        _fileLogger = fileLogger;
    }

    public event EventHandler<LogEntry>? Appended;

    public IReadOnlyList<LogEntry> Recent
    {
        get
        {
            lock (_gate)
            {
                return _recent.ToArray();
            }
        }
    }

    public void Write(LogLevel level, string source, string message)
    {
        var entry = new LogEntry(DateTimeOffset.Now, level, source, Redactor.MaskText(message));

        lock (_gate)
        {
            _recent.Add(entry);
            if (_recent.Count > MaxRecent)
            {
                _recent.RemoveRange(0, _recent.Count - MaxRecent);
            }
        }

        try
        {
            _fileLogger?.Write(ToSerilog(level), "[{Source}] {Message}", source, entry.Message);
        }
        catch (Exception)
        {
            // Сбой записи журнала не должен прерывать работу приложения.
        }

        try
        {
            Appended?.Invoke(this, entry);
        }
        catch (Exception)
        {
            // Обработчик интерфейса не должен ломать журнал.
        }
    }

    public void Clear()
    {
        lock (_gate)
        {
            _recent.Clear();
        }
    }

    private static Serilog.Events.LogEventLevel ToSerilog(LogLevel level) => level switch
    {
        LogLevel.Trace => Serilog.Events.LogEventLevel.Verbose,
        LogLevel.Debug => Serilog.Events.LogEventLevel.Debug,
        LogLevel.Information => Serilog.Events.LogEventLevel.Information,
        LogLevel.Warning => Serilog.Events.LogEventLevel.Warning,
        LogLevel.Error => Serilog.Events.LogEventLevel.Error,
        _ => Serilog.Events.LogEventLevel.Fatal
    };
}

/// <summary>Коллекция журнала, привязанная к интерфейсу (пополняется в UI-потоке).</summary>
public sealed class ObservableLogCollection : ObservableCollection<LogEntry>
{
}
